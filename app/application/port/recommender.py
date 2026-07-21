from typing import Protocol

from app.domain.models import (
    Place,
    RecommendationPlan,
    ScheduleContext,
    TodoRecommendation,
    Turn,
    UserProfile,
)


class Recommender(Protocol):
    """LLM 추천 포트. 구현은 infrastructure(OllamaRecommender 등).

    - recommend(계획 모드): '무엇을 할지 + 검색어'만 계획. 장소는 핸들러가 검색해 부착.
    - recommend_from_places(RAG 모드): 실제 후보를 주입받아 그중에서 골라 추천.
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
        focus: str = "",
        user_profile: UserProfile | None = None,
        history: list[Turn] | None = None,
        schedule_context: ScheduleContext | None = None,
    ) -> RecommendationPlan: ...

    async def recommend_from_places(
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
        schedule_context: ScheduleContext | None = None,
    ) -> TodoRecommendation: ...
