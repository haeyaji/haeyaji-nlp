import asyncio

from app.api.schemas import MessageRequest
from app.application.handler.chat_handler import ChatHandler


class _SpyResponder:
    def __init__(self):
        self.called = False

    async def respond(self, messages):
        self.called = True
        return "안녕하세요! 무엇을 도와드릴까요?"


def _handle(text):
    r = _SpyResponder()
    h = ChatHandler(r)
    resp = asyncio.run(h.handle(MessageRequest(text=text, lat=37.5, lng=127.0)))
    return resp, r


def test_greeting_uses_llm():
    resp, spy = _handle("안녕 넌 누구야?")
    assert spy.called  # 인사는 LLM 응답
    assert resp.intent == "chat"


def test_non_greeting_hard_declines_without_llm():
    # 규칙이 못 잡고 chat까지 온 비인사 요청 → LLM 안 태우고 거절 (leak 차단)
    resp, spy = _handle("아무말이나 자유롭게 해줘")
    assert not spy.called  # LLM 미호출
    assert "어려워요" in resp.reply
