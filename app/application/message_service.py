import re

from app.api.schemas import MessageRequest, MessageResponse
from app.application.action_rules import parse_action, parse_time_range
from app.application.category_map import queries_for
from app.application.category_selector import (
    category_intro,
    rejected_codes,
    select_categories,
)
from app.application.handler.action_handler import ActionHandler
from app.application.handler.handler import Handler
from app.application.intent_rules import blocked_reason
from app.application.location_extractor import extract_location_candidates
from app.application.port.geocoder import Geocoder
from app.application.port.intent_classifier import IntentClassifier
from app.application.query_mapper import is_broad_activity, keyword_from_text
from app.domain.models import Action

# 지역 접미사로 끝나는 키워드는 '검색어'가 아니라 '지역'이므로 검색어에서 제외.
# (강남역/성수동 → 제외, PC방/볼링장/방탈출카페 → 유지)
_GEO_SUFFIX = re.compile(r"(역|동|구|시|군|읍|면|리)$")

# 도메인 밖 / 인젝션 하드 거절 문구 (LLM 안 태우고 즉시 반환 → leak 원천차단)
_DECLINE_DOMAIN = (
    "그건 도와드리기 어려워요. 저는 오늘 갈 만한 곳이나 할 일을 추천해드려요. "
    "어떤 활동을 찾으세요?"
)
_DECLINE_INJECTION = "그건 도와드릴 수 없어요. 저는 오늘 갈 만한 곳·할 일 추천만 해드려요."
# 도메인밖+안 혼합("소풍가서 김치찌개 레시피")일 때 되는 부분을 살리며 앞에 붙이는 안내
_REDIRECT_NOTE = "그건 도와드리긴 어렵지만, 대신 갈 만한 곳을 추천해드릴게요!"


class MessageService:
    """인텐트 라우터: 분류(슬롯 추출) → 위치/검색어/정렬 좁히기 → 해당 핸들러로 분배.

    추천은 2단계다:
      1단계) 막연하면(구체 종류·선택 카테고리 없음) → 카테고리 후보(recommend_category)
      2단계) be가 selectedCategory를 실어 재호출 → 그 카테고리 안 장소 목록(recommend)
    사용자가 종류를 콕 집으면(맛집·PC방 등) 1단계를 건너뛰고 바로 장소를 추천한다.
    """

    def __init__(
        self,
        classifier: IntentClassifier,
        geocoder: Geocoder,
        recommend_handler: Handler,
        info_handler: Handler,
        chat_handler: Handler,
        action_handler: ActionHandler,
    ):
        self._classifier = classifier
        self._geocoder = geocoder
        self._action_handler = action_handler
        self._handlers: dict[str, Handler] = {
            "recommend": recommend_handler,
            "info": info_handler,
            "chat": chat_handler,
        }

    async def handle(self, req: MessageRequest) -> MessageResponse:
        # ⓪ [하드 거절] 도메인 밖·프롬프트 인젝션은 LLM 태우기 전에 규칙으로 즉시 차단.
        reason = blocked_reason(req.text)
        if reason == "injection":
            return MessageResponse(intent="chat", reply=_DECLINE_INJECTION, todos=[])
        if reason == "domain":
            # 도메인밖 + 도메인안(장소)이 섞이면 통째 거절하지 말고 되는 부분을 살린다.
            salvage = keyword_from_text(req.text)
            if salvage is not None:
                req = req.model_copy(update={"search_keywords": [salvage]})
                resp = await self._handlers["recommend"].handle(req)
                return resp.model_copy(
                    update={"reply": f"{_REDIRECT_NOTE} {resp.reply}".strip()}
                )
            return MessageResponse(intent="chat", reply=_DECLINE_DOMAIN, todos=[])

        # ⓪-b [액션] 일정 생성/공유 요청은 규칙 파서가 잡아 액션 핸들러로 (LLM 분류 전).
        action = parse_action(req.text)
        if action is not None:
            return await self._action_handler.handle(req, action)

        analysis = await self._classifier.classify(req.text, req.history)

        keywords: list[str] = []
        if analysis.intent in ("recommend", "info"):
            # [무엇] 분류기 검색어에서 지역명(강남역)·넓은 활동어(소풍/데이트) 제외.
            keywords = [
                k for k in analysis.keywords
                if not _GEO_SUFFIX.search(k) and not is_broad_activity(k)
            ]
            # ① [위치] 텍스트에 언급된 지역이 있으면 그곳을 검색 중심으로 (FR-3.10)
            req = await self._resolve_center(req, exclude=set(keywords))
            updates: dict = {}
            # ② [무엇] 남은 검색어(PC방·맛집 등)를 핸들러로 전달
            if keywords:
                updates["search_keywords"] = keywords
            # ③ [필터] "가까운"→거리순. 기본/"유명한"→정확도순(카카오 랭킹)
            if analysis.prefer == "near":
                updates["search_sort"] = "distance"
            if updates:
                req = req.model_copy(update=updates)

        # 시간 슬롯("1시 취소됐는데 그 시간에 할거") → schedule.fill 액션.
        # 1·2단계 응답 어디에 붙든 be가 그 슬롯을 유지하도록 recommend 계열에 실어준다.
        fill = parse_time_range(req.text) if analysis.intent == "recommend" else None
        fill_actions = [Action(type="schedule.fill", time_range=fill)] if fill else []

        if analysis.intent == "recommend":
            # [2단계] be가 고른 카테고리 → 그 카테고리 안에서만 장소 추천.
            if req.selected_category:
                queries = queries_for(req.selected_category)
                if queries:
                    req = req.model_copy(update={"search_keywords": queries})
                resp = await self._handlers["recommend"].handle(req)
                resp = self._tag_category(resp, req.selected_category)
                return self._with_actions(resp, fill_actions)

            # [1단계] 구체 종류가 없거나("오늘 뭐하지"), "카페 말고" 같은 재선택 →
            #         카테고리 후보 2~4개를 제시하고 be/fe가 하나 고르게 한다.
            rejected = rejected_codes(req.text)
            if rejected or not keywords:
                cats = select_categories(
                    req.weather, req.time_of_day, req.user_profile, exclude=rejected
                )
                return MessageResponse(
                    intent="recommend_category",
                    reply=category_intro(req.weather, req.time_of_day),
                    categories=cats,
                    actions=fill_actions,
                )
            # 구체 종류가 있으면(맛집·PC방 등) 1단계 건너뛰고 아래에서 바로 장소 추천.

        handler = self._handlers.get(analysis.intent, self._handlers["chat"])
        resp = await handler.handle(req)
        return self._with_actions(resp, fill_actions)

    @staticmethod
    def _with_actions(resp: MessageResponse, actions: list[Action]) -> MessageResponse:
        """recommend 응답에 schedule.fill 등 액션을 실어준다 (없으면 그대로)."""
        return resp.model_copy(update={"actions": actions}) if actions else resp

    @staticmethod
    def _tag_category(resp: MessageResponse, code: str) -> MessageResponse:
        """2단계 결과의 각 todo를 선택 카테고리 code로 태깅 통일 (7B 태깅 흔들림 방지)."""
        if not resp.todos:
            return resp
        todos = [t.model_copy(update={"category": code}) for t in resp.todos]
        return resp.model_copy(update={"todos": todos})

    async def _resolve_center(
        self, req: MessageRequest, exclude: set[str] | None = None
    ) -> MessageRequest:
        """텍스트에 지역 언급이 있고 지오코딩되면 그 좌표로 중심 이동. 없으면 원본.

        exclude(분류기가 뽑은 장소종류)와 장소종류 사전에 걸리는 후보는
        지역이 아니므로 건너뛴다. ("PC방 가고싶어"의 'PC방'이 중심이 되면 안 됨)
        """
        for candidate in extract_location_candidates(req.text):
            if exclude and candidate in exclude:
                continue  # 분류기가 '찾는 장소 종류'로 본 단어
            if keyword_from_text(candidate) is not None:
                continue  # 장소종류 사전에 걸림 (밥집/카페 등)
            coords = await self._geocoder.geocode(candidate)
            if coords is not None:
                lat, lng = coords
                return req.model_copy(update={"lat": lat, "lng": lng})
        return req
