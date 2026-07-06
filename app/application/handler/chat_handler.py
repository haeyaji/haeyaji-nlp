from app.api.schemas import MessageRequest, MessageResponse
from app.application.intent_rules import is_greeting
from app.infrastructure.llm.prompt import build_chat_messages
from app.application.port.chat_responder import ChatResponder

# 인사가 아닌데 chat까지 온 것 = 규칙이 못 잡은 도메인 밖 요청 → LLM 안 태우고 거절.
# (chat LLM에 free-form을 맡기면 레시피·코드 등을 그냥 해줘버리는 leak 발생)
_DECLINE = (
    "그건 도와드리기 어려워요. 저는 오늘 갈 만한 곳이나 할 일을 추천해드려요. "
    "어떤 활동을 찾으세요?"
)


class ChatHandler:
    """잡담 인텐트: 인사·자기소개성만 LLM으로 친근히, 그 외는 정중히 거절."""

    def __init__(self, responder: ChatResponder):
        self._responder = responder

    async def handle(self, req: MessageRequest) -> MessageResponse:
        # 인사류만 자유 응답 허용, 나머지는 하드 거절 (free-form leak 차단)
        if not is_greeting(req.text):
            return MessageResponse(intent="chat", reply=_DECLINE, todos=[])
        reply = await self._responder.respond(build_chat_messages(req.text, req.history))
        return MessageResponse(intent="chat", reply=reply, todos=[])
