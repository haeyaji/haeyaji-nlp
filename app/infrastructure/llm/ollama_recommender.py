import ollama

from app.domain.models import Place, TodoRecommendation, Turn, UserProfile
from app.infrastructure.llm.prompt import build_messages


class OllamaRecommender:
    """Recommender 포트의 Ollama 구현.

    JSON 스키마 강제 출력(format)으로 항상 TodoRecommendation 구조를 받는다.
    나중에 파인튜닝 모델로 바꾸려면 model 이름만 교체하면 된다.
    """

    def __init__(self, host: str, model: str):
        self._client = ollama.AsyncClient(host=host)
        self._model = model
        self._schema = TodoRecommendation.model_json_schema()

    async def recommend(
        self,
        *,
        weather: str,
        mood: str,
        time_of_day: str,
        weekday: str,
        places: list[Place],
        note: str = "",
        user_profile: UserProfile | None = None,
        history: list[Turn] | None = None,
    ) -> TodoRecommendation:
        messages = build_messages(
            weather=weather,
            mood=mood,
            time_of_day=time_of_day,
            weekday=weekday,
            places=places,
            note=note,
            user_profile=user_profile,
            history=history,
        )
        resp = await self._client.chat(
            model=self._model,
            messages=messages,
            format=self._schema,  # JSON 스키마 강제
            options={"temperature": 0.7},
        )
        # 스키마 강제라 content는 유효한 JSON → pydantic으로 검증/파싱
        return TodoRecommendation.model_validate_json(resp["message"]["content"])
