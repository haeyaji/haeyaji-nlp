from typing import Protocol

from app.api.schemas import MessageRequest, MessageResponse


class Handler(Protocol):
    """인텐트별 처리기. 각자 한 가지 일만 한다 (작은 모델 안정성)."""

    async def handle(self, req: MessageRequest) -> MessageResponse: ...
