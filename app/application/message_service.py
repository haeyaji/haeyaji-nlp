import re

from app.api.schemas import MessageRequest, MessageResponse
from app.application.handler.handler import Handler
from app.application.intent_rules import blocked_reason
from app.application.location_extractor import extract_location_candidates
from app.application.option_builder import branch_question, pick_options
from app.application.port.geocoder import Geocoder
from app.application.port.intent_classifier import IntentClassifier
from app.application.query_mapper import keyword_from_text

# 지역 접미사로 끝나는 키워드는 '검색어'가 아니라 '지역'이므로 검색어에서 제외.
# (강남역/성수동 → 제외, PC방/볼링장/방탈출카페 → 유지)
_GEO_SUFFIX = re.compile(r"(역|동|구|시|군|읍|면|리)$")

# 도메인 밖 / 인젝션 하드 거절 문구 (LLM 안 태우고 즉시 반환 → leak 원천차단)
_DECLINE_DOMAIN = (
    "그건 도와드리기 어려워요. 저는 오늘 갈 만한 곳이나 할 일을 추천해드려요. "
    "어떤 활동을 찾으세요?"
)
_DECLINE_INJECTION = "그건 도와드릴 수 없어요. 저는 오늘 갈 만한 곳·할 일 추천만 해드려요."

# LLM이 질문 생성에 실패했을 때 쓰는 기본 되묻기 문장 (반드시 '?'로 끝남 — 캡 카운트 마커)
_CLARIFY_REPLY = "어떤 걸 찾으세요?"

# 되묻기 최대 횟수 — 이만큼 좁혔으면 다음 턴엔 무조건 추천 (무한 질문 방지)
_MAX_NARROW_ROUNDS = 2


class MessageService:
    """인텐트 라우터: 분류(슬롯 추출) → 위치/검색어/정렬 좁히기 → 해당 핸들러로 분배.

    '하나의 만능 프롬프트'가 아니라 분류 후 좁은 핸들러로 보내는 게
    작은 모델을 안정적으로 쓰는 핵심. 요청은 슬롯(위치/무엇/필터)이 채워진
    만큼 좁혀지고, 빈 슬롯은 맥락(날씨·기분)과 기본값으로 채운다.
    """

    def __init__(
        self,
        classifier: IntentClassifier,
        geocoder: Geocoder,
        recommend_handler: Handler,
        info_handler: Handler,
        chat_handler: Handler,
    ):
        self._classifier = classifier
        self._geocoder = geocoder
        self._handlers: dict[str, Handler] = {
            "recommend": recommend_handler,
            "info": info_handler,
            "chat": chat_handler,
        }

    async def handle(self, req: MessageRequest) -> MessageResponse:
        # ⓪ [하드 거절] 도메인 밖·프롬프트 인젝션은 LLM 태우기 전에 규칙으로 즉시 차단.
        #    (7B 모델은 프롬프트로 "거절해" 해도 안 지켜서 leak → 코드로 원천차단 + 빠름)
        reason = blocked_reason(req.text)
        if reason == "injection":
            return MessageResponse(intent="chat", reply=_DECLINE_INJECTION, todos=[])
        if reason == "domain":
            return MessageResponse(intent="chat", reply=_DECLINE_DOMAIN, todos=[])

        analysis = await self._classifier.classify(req.text, req.history)

        if analysis.intent in ("recommend", "info"):
            # [무엇] 분류기가 뽑은 검색어에서 지역명 제거 (지역은 검색 중심으로만 씀)
            keywords = [k for k in analysis.keywords if not _GEO_SUFFIX.search(k)]
            # ① [위치] 텍스트에 언급된 지역이 있으면 그곳을 검색 중심으로 (FR-3.10)
            #    장소종류 단어(PC방·밥집 등)는 지역이 아니므로 후보에서 제외.
            #    (exclude는 지역명을 걸러낸 keywords만 — '강남역'이 keywords에 섞여도
            #     위치 해석을 막으면 안 되기 때문)
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

        # ④ [좁힘 — 포위망] LLM이 "카테고리 정보 부족"이라 판단하면 되묻기.
        #    질문·선택지는 LLM이 단계에 맞게 생성(1단계 큰 갈래 → 2단계 세부),
        #    fe가 버튼으로 렌더하고 클릭 텍스트가 다음 메시지로 온다.
        #    코드 안전장치: 최대 _MAX_NARROW_ROUNDS회 — 넘으면 무조건 추천 진행.
        if analysis.intent == "recommend" and self._narrow_rounds(req.history) < _MAX_NARROW_ROUNDS:
            if analysis.vague:
                # LLM이 부족 판단 → LLM 생성 질문/선택지 (부실하면 규칙 폴백)
                question = analysis.question.strip() or _CLARIFY_REPLY
                options = self._clean_options(analysis.options) or pick_options(
                    req.weather, req.time_of_day
                )
                return MessageResponse(
                    intent="recommend", reply=question, todos=[], options=options
                )
            # 코드 백스톱: 답이 '큰 갈래'(먹으러 가기 등)인데 LLM이 되묻기를
            # 건너뛰었으면 세부 질문을 강제한다 (포위망 2단계 보장)
            branch = branch_question(req.text)
            if branch is not None:
                question, options = branch
                return MessageResponse(
                    intent="recommend", reply=question, todos=[], options=options
                )

        handler = self._handlers.get(analysis.intent, self._handlers["chat"])
        return await handler.handle(req)

    @staticmethod
    def _narrow_rounds(history: list) -> int:
        """직전 대화에서 이미 몇 번 좁혔는지 — '?'로 끝나는 assistant 턴 수(최근 6턴)."""
        recent = history[-6:] if history else []
        return sum(
            1 for t in recent if t.role == "assistant" and t.content.rstrip().endswith("?")
        )

    @staticmethod
    def _clean_options(options: list[str]) -> list[str]:
        """LLM 생성 선택지 검증: 공백/중복 제거, 2~6개 아니면 []( → 규칙 칩 폴백)."""
        seen: set[str] = set()
        cleaned: list[str] = []
        for opt in options:
            opt = opt.strip()
            if opt and opt not in seen and len(opt) <= 12:
                seen.add(opt)
                cleaned.append(opt)
        return cleaned[:6] if len(cleaned) >= 2 else []

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
