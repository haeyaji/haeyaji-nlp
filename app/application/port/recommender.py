from typing import Protocol

from app.domain.models import RecommendationPlan, Turn, UserProfile


class Recommender(Protocol):
    """LLM 추천 포트. 구현은 infrastructure(OllamaRecommender 등).

    LLM은 '무엇을 할지(활동) + 검색어'만 계획한다. 실제 장소 검색/부착은 핸들러가 한다.
    나중에 파인튜닝 모델로 교체해도 이 인터페이스는 그대로 유지된다.
    """

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
    ) -> RecommendationPlan: ...
