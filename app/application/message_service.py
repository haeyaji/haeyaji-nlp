from app.api.schemas import MessageRequest, MessageResponse
from app.application.handler.handler import Handler
from app.application.location_extractor import extract_location_candidates
from app.application.port.geocoder import Geocoder
from app.application.port.intent_classifier import IntentClassifier


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
        intent = await self._classifier.classify(req.text, req.history)

        # 추천/정보는 텍스트에 언급된 지역이 있으면 그곳을 검색 중심으로 (FR-3.10)
        if intent in ("recommend", "info"):
            req = await self._resolve_center(req)

        handler = self._handlers.get(intent, self._handlers["chat"])
        return await handler.handle(req)

    async def _resolve_center(self, req: MessageRequest) -> MessageRequest:
        """텍스트에 지역 언급이 있고 지오코딩되면 그 좌표로 중심 이동. 없으면 원본."""
        for candidate in extract_location_candidates(req.text):
            coords = await self._geocoder.geocode(candidate)
            if coords is not None:
                lat, lng = coords
                return req.model_copy(update={"lat": lat, "lng": lng})
        return req
