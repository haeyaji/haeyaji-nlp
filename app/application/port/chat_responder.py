from typing import Protocol


class ChatResponder(Protocol):
    """범용 텍스트 응답 포트 (정보/잡답 핸들러가 사용)."""

    async def respond(self, messages: list[dict]) -> str: ...
