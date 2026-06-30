import asyncio

from app.api.schemas import MessageRequest, MessageResponse
from app.application.port.place_finder import PlaceFinder
from app.application.port.recommender import Recommender
from app.application.query_mapper import pick_search_queries
from app.domain.models import Place


class RecommendHandler:
    """추천 인텐트: 규칙 → 카카오(병렬) → LLM 추천 → 로그.

    기존 RAG 파이프라인이 그대로 여기로 들어왔다.
    포트(PlaceFinder, Recommender)에만 의존하므로 구현 교체에 영향 없음.
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

        # ① 규칙으로 검색어 결정  ② 카카오 병렬 검색 → 중복 제거
        queries = pick_search_queries(req.weather, req.mood, req.text)
        results = await asyncio.gather(
            *(
                self._places.search(q, req.lat, req.lng, radius, self._size)
                for q in queries
            )
        )
        places: list[Place] = []
        seen: set[str] = set()
        for place_list in results:
            for p in place_list:
                if p.name not in seen:
                    seen.add(p.name)
                    places.append(p)

        # ③ LLM 추천 (사용자 자유 텍스트는 note로 반영)
        rec = await self._recommender.recommend(
            weather=req.weather,
            mood=req.mood,
            time_of_day=req.time_of_day,
            weekday=req.weekday,
            places=places,
            note=req.text,
            user_profile=req.user_profile,
            history=req.history,
        )

        # ④ 로그 (미래 학습데이터)
        self._logger.log(request=req.model_dump(), places=places, result=rec)
        return MessageResponse(intent="recommend", reply=rec.analysis, todos=rec.todos)
