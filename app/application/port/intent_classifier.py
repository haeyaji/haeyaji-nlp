from typing import Protocol

from app.domain.models import Analysis, Turn


class IntentClassifier(Protocol):
    """사용자 메시지를 intent + 검색 keywords로 분석하는 포트."""

    async def classify(self, text: str, history: list[Turn] | None = None) -> Analysis: ...
