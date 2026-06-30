import ollama
from pydantic import BaseModel

from app.application.intent_rules import rule_intent
from app.domain.models import Intent, Turn
from app.infrastructure.llm.prompt import build_classify_messages


class _IntentResult(BaseModel):
    intent: Intent


class OllamaIntentClassifier:
    """IntentClassifier 포트의 Ollama 구현. 스키마 강제로 enum 하나만 받는다."""

    def __init__(self, host: str, model: str):
        self._client = ollama.AsyncClient(host=host)
        self._model = model
        self._schema = _IntentResult.model_json_schema()

    async def classify(self, text: str, history: list[Turn] | None = None) -> Intent:
        # ① 규칙으로 확실한 케이스 선분류 (코딩/번역 등 도메인 밖 작업)
        forced = rule_intent(text)
        if forced is not None:
            return forced

        # ② 애매하면 LLM 분류 (직전 대화 맥락 포함)
        resp = await self._client.chat(
            model=self._model,
            messages=build_classify_messages(text, history),
            format=self._schema,
            options={"temperature": 0},  # 분류는 결정적으로
        )
        return _IntentResult.model_validate_json(resp["message"]["content"]).intent
