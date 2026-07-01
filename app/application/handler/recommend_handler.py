import asyncio

import httpx

from app.api.schemas import MessageRequest, MessageResponse
from app.application.port.place_finder import PlaceFinder
from app.application.port.recommender import Recommender
from app.application.query_mapper import keyword_from_text
from app.domain.models import Place, PlannedTodo, TodoItem, TodoRecommendation


class RecommendHandler:
    """추천 인텐트: LLM이 활동+검색어 계획 → 각 검색어로 카카오 검색 → 실제 장소 부착.

    LLM은 가게 이름을 지어내지 않고 '무엇을(활동)+어떤 곳(검색어)'만 정한다.
    코드가 카카오에서 실제 장소를 채우므로 장소 환각이 원천 차단된다.
    """

    def __init__(
        self,
        place_finder: PlaceFinder,
        recommender: Recommender,
        logger,
        default_radius_m: int,
        places_per_query: int,
    ):
        self._places = place_finder
        self._recommender = recommender
        self._logger = logger
        self._default_radius = default_radius_m
        self._size = places_per_query

    async def handle(self, req: MessageRequest) -> MessageResponse:
        radius = req.radius_m or self._default_radius

        # ① LLM이 활동 + 검색어 계획 (장소 아직 없음)
        plan = await self._recommender.recommend(
            weather=req.weather,
            mood=req.mood,
            time_of_day=req.time_of_day,
            weekday=req.weekday,
            note=req.text,
            user_profile=req.user_profile,
            history=req.history,
        )

        # ② 각 활동의 검색 후보를 병렬로 모으고
        candidates = await asyncio.gather(
            *(self._search(p, req.lat, req.lng, radius) for p in plan.todos)
        )

        # ③ 서로 다른 장소로 배정 (같은 곳 중복 방지)
        used: set[str] = set()
        todos: list[TodoItem] = []
        for planned, places in zip(plan.todos, candidates):
            todos.append(self._assign(planned, places, used))

        result = TodoRecommendation(analysis=plan.analysis, todos=todos)
        self._logger.log(request=req.model_dump(), places=[], result=result)
        return MessageResponse(intent="recommend", reply=plan.analysis, todos=todos)

    async def _search(
        self, planned: PlannedTodo, lat: float, lng: float, radius: int
    ) -> list[Place]:
        """검색어 후보(LLM 검색어 → 제목 키워드)로 카카오 검색. 결과 있으면 반환.

        집/온라인 활동은 두 후보 모두 비어 [] 반환(장소 안 붙음).
        LLM이 검색 안 되는 문구를 넣어도 제목 키워드로 복구된다.
        """
        queries: list[str] = []
        if planned.search_query:
            queries.append(planned.search_query)
        title_kw = keyword_from_text(planned.title)
        if title_kw and title_kw not in queries:
            queries.append(title_kw)

        for query in queries:
            try:
                places = await self._places.search(
                    query, lat, lng, radius, self._size, sort="accuracy"
                )
            except (httpx.HTTPError, KeyError, ValueError):
                continue  # 검색 실패 → 다음 후보
            if places:
                return places
        return []

    @staticmethod
    def _assign(planned: PlannedTodo, places: list[Place], used: set[str]) -> TodoItem:
        """후보 중 아직 안 쓴 첫 장소를 붙인다(정확도순). 없으면 장소 없이."""
        item = TodoItem(
            title=planned.title,
            reason=planned.reason,
            category=planned.category,
            estimated_minutes=planned.estimated_minutes,
        )
        for p in places:
            if p.name not in used:
                used.add(p.name)
                item.place_name = p.name
                item.place_url = p.url or None
                item.x = p.x
                item.y = p.y
                item.distance_m = p.distance_m
                break
        return item
