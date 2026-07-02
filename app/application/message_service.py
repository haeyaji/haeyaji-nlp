import re

from app.api.schemas import MessageRequest, MessageResponse
from app.application.handler.handler import Handler
from app.application.location_extractor import extract_location_candidates
from app.application.port.geocoder import Geocoder
from app.application.port.intent_classifier import IntentClassifier
from app.application.query_mapper import keyword_from_text

# 지역 접미사로 끝나는 키워드는 '검색어'가 아니라 '지역'이므로 검색어에서 제외.
# (강남역/성수동 → 제외, PC방/볼링장/방탈출카페 → 유지)
_GEO_SUFFIX = re.compile(r"(역|동|구|시|군|읍|면|리)$")

# 막연한 요청 + 맥락(기분/대화)도 없을 때 1회 되묻는 문장
_CLARIFY_REPLY = (
    "어떤 걸 찾으세요? 예를 들어 '조용한 카페', '가까운 밥집', '놀 만한 데'처럼 "
    "말해주시면 날씨에 맞춰 딱 맞게 추천해드릴게요."
)

# 막연하지만 맥락으로 추천은 가능할 때, 결과 뒤에 붙이는 좁히기 안내
_NARROW_HINT = " 더 구체적으로 말해주시면(예: '조용한 카페', '유명한 밥집') 취향에 맞게 좁혀드릴게요."


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

        # ④ [좁힘] 막연한 요청인데 좁힐 맥락(기분·대화)조차 없으면 1회 되묻기
        if (
            analysis.intent == "recommend"
            and analysis.vague
            and not req.search_keywords
            and not req.mood
            and not req.history
        ):
            return MessageResponse(intent="recommend", reply=_CLARIFY_REPLY, todos=[])

        handler = self._handlers.get(analysis.intent, self._handlers["chat"])
        resp = await handler.handle(req)

        # 막연했지만 맥락으로 추천한 경우 → 좁히기 안내를 덧붙임 (다음 턴에 더 좁혀짐)
        if analysis.intent == "recommend" and analysis.vague and resp.todos:
            resp = resp.model_copy(update={"reply": resp.reply + _NARROW_HINT})
        return resp

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
