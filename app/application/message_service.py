import re

from app.api.schemas import MessageRequest, MessageResponse
from app.application.handler.handler import Handler
from app.application.location_extractor import extract_location_candidates
from app.application.port.geocoder import Geocoder
from app.application.port.intent_classifier import IntentClassifier

# 지역 접미사로 끝나는 키워드는 '검색어'가 아니라 '지역'이므로 검색어에서 제외.
# (강남역/성수동 → 제외, PC방/볼링장/방탈출카페 → 유지)
_GEO_SUFFIX = re.compile(r"(역|동|구|시|군|읍|면|리)$")


class MessageService:
    """인텐트 라우터: (위치 해석) → 분류 → 해당 핸들러로 분배.

    '하나의 만능 프롬프트'가 아니라 분류 후 좁은 핸들러로 보내는 게
    작은 모델을 안정적으로 쓰는 핵심.
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
            # ① 텍스트에 언급된 지역이 있으면 그곳을 검색 중심으로 (FR-3.10)
            req = await self._resolve_center(req)
            # ② 분류기가 뽑은 검색어(PC방·맛집 등)를 핸들러로 전달
            #    (지역명이 섞여 나오면 제외 — 지역은 검색 중심으로만 씀)
            keywords = [k for k in analysis.keywords if not _GEO_SUFFIX.search(k)]
            if keywords:
                req = req.model_copy(update={"search_keywords": keywords})

        handler = self._handlers.get(analysis.intent, self._handlers["chat"])
        return await handler.handle(req)

    async def _resolve_center(self, req: MessageRequest) -> MessageRequest:
        """텍스트에 지역 언급이 있고 지오코딩되면 그 좌표로 중심 이동. 없으면 원본."""
        for candidate in extract_location_candidates(req.text):
            coords = await self._geocoder.geocode(candidate)
            if coords is not None:
                lat, lng = coords
                return req.model_copy(update={"lat": lat, "lng": lng})
        return req
