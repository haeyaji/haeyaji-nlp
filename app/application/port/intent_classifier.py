from typing import Protocol

from app.domain.models import Intent, Turn


class IntentClassifier(Protocol):
    """사용자 메시지를 intent(recommend/info/chat)로 분류하는 포트."""

    async def classify(self, text: str, history: list[Turn] | None = None) -> Intent: ...
