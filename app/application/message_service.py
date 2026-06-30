from app.api.schemas import MessageRequest, MessageResponse
from app.application.handler.handler import Handler
from app.application.port.intent_classifier import IntentClassifier


class MessageService:
    """인텐트 라우터: 분류 → 해당 핸들러로 분배.

    '하나의 만능 프롬프트'가 아니라 분류 후 좁은 핸들러로 보내는 게
    작은 모델을 안정적으로 쓰는 핵심.
    """

    def __init__(
        self,
        classifier: IntentClassifier,
        recommend_handler: Handler,
        info_handler: Handler,
        chat_handler: Handler,
    ):
        self._classifier = classifier
        self._handlers: dict[str, Handler] = {
            "recommend": recommend_handler,
            "info": info_handler,
            "chat": chat_handler,
        }

    async def handle(self, req: MessageRequest) -> MessageResponse:
        intent = await self._classifier.classify(req.text, req.history)
        handler = self._handlers.get(intent, self._handlers["chat"])
        return await handler.handle(req)
