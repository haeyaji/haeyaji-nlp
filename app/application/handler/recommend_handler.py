import asyncio

import httpx

from app.api.schemas import MessageRequest, MessageResponse
from app.application.port.place_finder import PlaceFinder
from app.application.port.recommender import Recommender
from app.application.query_mapper import category_code_for, keyword_from_text
from app.domain.models import Place, PlannedTodo, TodoItem, TodoRecommendation

# RAG 경로에서 LLM에 보여줄 후보 수 (카카오 keyword 검색 size 최대 15)
_RAG_CANDIDATE_SIZE = 15


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

        # 검색어가 확정됐으면(포위망 종착/명시 요청) RAG 경로: 검색 먼저 → 후보 주입 → LLM 선택.
        # 아직 막연하면(검색어 없음) 계획 경로: LLM 계획 → 검색 부착.
        if req.search_keywords:
            return await self._recommend_rag(req, radius)
        return await self._recommend_plan(req, radius)

    async def _recommend_plan(self, req: MessageRequest, radius: int) -> MessageResponse:
        # ① LLM이 활동 + 검색어 계획 (장소 아직 없음)
        #    확정된 종류(search_keywords)가 있으면 그 종류로만 계획 (몰빵 고정)
        plan = await self._recommender.recommend(
            weather=req.weather,
            mood=req.mood,
            time_of_day=req.time_of_day,
            weekday=req.weekday,
            note=req.text,
            focus=", ".join(req.search_keywords),
            user_profile=req.user_profile,
            history=req.history,
        )

        # ①-b 확정 종류의 카테고리 코드(맛집→FD6 등)가 있으면, 다른 종류의 계획을
        #     코드로 걸러낸다 (LLM이 focus 지시를 어기고 카페 등을 끼워넣는 것 방지)
        focus_codes = {
            code for kw in req.search_keywords if (code := category_code_for(kw))
        }
        todos_plan = plan.todos
        if focus_codes:
            kept = [
                p
                for p in todos_plan
                if not p.search_query
                or category_code_for(p.search_query) in focus_codes
                or category_code_for(p.search_query) is None
            ]
            todos_plan = kept or todos_plan  # 전부 걸러지면 원본 유지 (빈 추천 방지)

        # ② 각 활동의 검색 후보를 병렬로 모으고 (정렬은 요청 필터 슬롯: 가까운→distance)
        candidates = await asyncio.gather(
            *(
                self._search(p, req.lat, req.lng, radius, req.search_sort, focus_codes)
                for p in todos_plan
            )
        )

        # ③ 서로 다른 장소로 배정 (같은 곳 중복 방지)
        used: set[str] = set()
        todos: list[TodoItem] = []
        for planned, places in zip(todos_plan, candidates):
            todos.append(self._assign(planned, places, used))

        result = TodoRecommendation(analysis=plan.analysis, todos=todos)
        self._logger.log(request=req.model_dump(), places=[], result=result)
        return MessageResponse(intent="recommend", reply=plan.analysis, todos=todos)

    async def _recommend_rag(self, req: MessageRequest, radius: int) -> MessageResponse:
        """RAG 경로: 확정 검색어로 카카오 검색 → 후보를 LLM에 주입 → LLM이 선택.

        검색이 LLM 생성 품질을 올리는 진짜 RAG. 후보가 없으면 계획 경로로 폴백.
        """
        # ① 확정 검색어별 병렬 검색 → 후보 풀 구성 (중복 제거, 카테고리 필터·정렬 적용)
        focus_codes = {
            code for kw in req.search_keywords if (code := category_code_for(kw))
        }
        single_code = next(iter(focus_codes)) if len(focus_codes) == 1 else None
        results = await asyncio.gather(
            *(
                self._safe_search(
                    kw, req.lat, req.lng, radius, req.search_sort,
                    category_code_for(kw) or single_code, size=_RAG_CANDIDATE_SIZE,
                )
                for kw in req.search_keywords
            )
        )
        candidates: list[Place] = []
        seen: set[str] = set()
        for places in results:
            for p in places:
                if p.name not in seen:
                    seen.add(p.name)
                    candidates.append(p)

        # 후보가 없으면 검색으로 얻을 게 없음 → 계획 경로(집/실내 활동 등)로 폴백
        if not candidates:
            return await self._recommend_plan(req, radius)

        # ② LLM이 실제 후보 목록을 보고 골라 추천 (환각 가드는 recommender가 수행)
        rec = await self._recommender.recommend_from_places(
            weather=req.weather,
            mood=req.mood,
            time_of_day=req.time_of_day,
            weekday=req.weekday,
            places=candidates,
            note=req.text,
            user_profile=req.user_profile,
            history=req.history,
        )
        self._logger.log(request=req.model_dump(), places=candidates, result=rec)
        return MessageResponse(intent="recommend", reply=rec.analysis, todos=rec.todos)

    async def _safe_search(
        self, query: str, lat: float, lng: float, radius: int, sort: str,
        code: str | None, size: int,
    ) -> list[Place]:
        """카카오 검색 1건 — 실패 시 [] (RAG 후보 수집이 한 검색 실패로 죽지 않게)."""
        try:
            return await self._places.search(
                query, lat, lng, radius, size, sort=sort, category_group_code=code
            )
        except (httpx.HTTPError, KeyError, ValueError):
            return []

    async def _search(
        self,
        planned: PlannedTodo,
        lat: float,
        lng: float,
        radius: int,
        sort: str,
        focus_codes: set[str] | None = None,
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
            # 아는 검색어는 카카오 카테고리 하드 필터 (맛집=FD6 → 카페 섞임 차단).
            # 모르는 검색어("현지 맛집" 등)라도 확정 종류가 하나면 그 코드로 강제.
            code = category_code_for(query)
            if code is None and focus_codes and len(focus_codes) == 1:
                code = next(iter(focus_codes))
            try:
                places = await self._places.search(
                    query, lat, lng, radius, self._size, sort=sort,
                    category_group_code=code,
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
