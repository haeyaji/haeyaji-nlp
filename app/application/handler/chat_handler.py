from app.api.schemas import MessageRequest, MessageResponse
from app.application.port.chat_responder import ChatResponder
from app.infrastructure.llm.prompt import build_chat_messages


class ChatHandler:
    """잡담 인텐트: 가볍게 응답하고, 범위 밖 깊은 주제는 정중히 안내."""

    def __init__(self, responder: ChatResponder):
        self._responder = responder

    async def handle(self, req: MessageRequest) -> MessageResponse:
        reply = await self._responder.respond(build_chat_messages(req.text, req.history))
        return MessageResponse(intent="chat", reply=reply, todos=[])
