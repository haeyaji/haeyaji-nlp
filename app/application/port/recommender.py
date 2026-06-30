from typing import Protocol

from app.domain.models import Place, TodoRecommendation, Turn, UserProfile


class Recommender(Protocol):
    """LLM 추천 포트. 구현은 infrastructure(OllamaRecommender 등).

    나중에 파인튜닝 모델로 교체해도 이 인터페이스는 그대로 유지된다.
    """

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
    ) -> TodoRecommendation: ...
