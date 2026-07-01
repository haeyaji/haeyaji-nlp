import ollama

from app.application.intent_rules import rule_intent
from app.domain.models import Analysis, Turn
from app.infrastructure.llm.prompt import build_classify_messages


class OllamaIntentClassifier:
    """IntentClassifier 포트의 Ollama 구현.

    intent + keywords(찾는 장소 종류)를 함께 추출한다(호출 1회로).
    """

    def __init__(self, host: str, model: str):
        self._client = ollama.AsyncClient(host=host)
        self._model = model
        self._schema = Analysis.model_json_schema()

    async def classify(self, text: str, history: list[Turn] | None = None) -> Analysis:
        # ① 규칙으로 확실한 케이스 선분류 (코딩/번역 등 도메인 밖 작업 → chat)
        forced = rule_intent(text)
        if forced is not None:
            return Analysis(intent=forced, keywords=[])

        # ② 애매하면 LLM 분류 + 키워드 추출 (직전 대화 맥락 포함)
        resp = await self._client.chat(
            model=self._model,
            messages=build_classify_messages(text, history),
            format=self._schema,
            options={"temperature": 0},  # 분류는 결정적으로
        )
        return Analysis.model_validate_json(resp["message"]["content"])
