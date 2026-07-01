import ollama

from app.domain.models import RecommendationPlan, Turn, UserProfile
from app.infrastructure.llm.prompt import build_messages


class OllamaRecommender:
    """Recommender 포트의 Ollama 구현.

    LLM은 '무엇을 할지(활동) + 검색어(search_query)'만 계획한다.
    실제 장소(이름/좌표)는 핸들러가 카카오에서 검색해 붙인다 → 장소 이름 환각 원천 차단.
    나중에 파인튜닝 모델로 바꾸려면 model 이름만 교체하면 된다.
    """

    def __init__(self, host: str, model: str):
        self._client = ollama.AsyncClient(host=host)
        self._model = model
        self._schema = RecommendationPlan.model_json_schema()

    async def recommend(
        self,
        *,
        weather: str,
        mood: str,
        time_of_day: str,
        weekday: str,
        note: str = "",
        user_profile: UserProfile | None = None,
        history: list[Turn] | None = None,
    ) -> RecommendationPlan:
        messages = build_messages(
            weather=weather,
            mood=mood,
            time_of_day=time_of_day,
            weekday=weekday,
            note=note,
            user_profile=user_profile,
            history=history,
        )
        resp = await self._client.chat(
            model=self._model,
            messages=messages,
            format=self._schema,  # 계획 스키마 강제
            options={"temperature": 0.5},  # 검색어 채움 일관성 위해 약간 낮춤
        )
        return RecommendationPlan.model_validate_json(resp["message"]["content"])
