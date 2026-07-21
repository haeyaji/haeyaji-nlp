import asyncio

from app.api.schemas import MessageRequest
from app.application.handler.recommend_handler import RecommendHandler
from app.domain.models import (
    Place,
    PlannedTodo,
    RecommendationPlan,
    ScheduleContext,
    TodoItem,
    TodoRecommendation,
)


class _FakeRecommender:
    def __init__(self):
        self.rag_called_with: list[Place] | None = None

    async def recommend(self, **kwargs):
        return RecommendationPlan(
            analysis="비 오는 오후",
            todos=[
                PlannedTodo(title="북카페서 책", reason="r", category="휴식",
                            estimated_minutes=60, search_query="북카페"),
                PlannedTodo(title="집 스트레칭", reason="r", category="휴식",
                            estimated_minutes=10, search_query=None),
            ],
        )

    async def recommend_from_places(self, *, places, **kwargs):
        # RAG 경로: 주입된 후보 중 첫 번째를 골랐다고 가정
        self.rag_called_with = places
        first = places[0]
        return TodoRecommendation(
            analysis="후보 기반 추천",
            todos=[
                TodoItem(
                    title=f"{first.name} 방문", reason="가까움", category="맛집/카페",
                    estimated_minutes=60, place_name=first.name,
                    place_url=first.url or None, x=first.x, y=first.y,
                    distance_m=first.distance_m,
                )
            ],
        )


class _FakePlaceFinder:
    async def search(
        self, query, lat, lng, radius_m, size=5, sort="accuracy", category_group_code=None
    ):
        return [
            Place(name="OO북카페", category="카페", address="서울",
                  url="http://k/1", distance_m=100, x=127.0, y=37.5)
        ]


class _FakePlaceFinderEmpty:
    async def search(self, *a, **k):
        return []


def _handle(place_finder):
    h = RecommendHandler(place_finder, _FakeRecommender(), 1500, 5)
    return asyncio.run(h.handle(MessageRequest(text="비 오는데 뭐하지", lat=37.5, lng=127.0)))


def test_attaches_place_for_search_query():
    resp = _handle(_FakePlaceFinder())
    assert resp.intent == "recommend"
    assert len(resp.todos) == 2
    # search_query 있는 활동 → 실제 장소 부착
    assert resp.todos[0].place_name == "OO북카페"
    assert resp.todos[0].distance_m == 100
    # search_query None인 활동 → 장소 없음
    assert resp.todos[1].place_name is None


def test_placeless_when_no_results():
    # 검색 결과가 없어도 활동(계획)은 유지, 장소만 빔 (graceful)
    resp = _handle(_FakePlaceFinderEmpty())
    assert len(resp.todos) == 2
    assert resp.todos[0].place_name is None


def test_rag_path_when_keywords_confirmed():
    # 검색어 확정 → RAG 경로: 검색 먼저 → 후보를 recommender에 주입 → LLM 선택
    rec = _FakeRecommender()
    h = RecommendHandler(_FakePlaceFinder(), rec, 1500, 5)
    req = MessageRequest(text="한식 먹고싶어", lat=37.5, lng=127.0, search_keywords=["한식"])
    resp = asyncio.run(h.handle(req))
    assert rec.rag_called_with is not None  # RAG 경로 탐 (후보 주입됨)
    assert resp.todos[0].place_name == "OO북카페"  # 후보 기반 결과
    assert resp.reply == "후보 기반 추천"


def test_rag_falls_back_to_plan_when_no_candidates():
    # 검색어 확정이어도 후보가 0이면 계획 경로로 폴백
    rec = _FakeRecommender()
    h = RecommendHandler(_FakePlaceFinderEmpty(), rec, 1500, 5)
    req = MessageRequest(text="한식 먹고싶어", lat=37.5, lng=127.0, search_keywords=["한식"])
    resp = asyncio.run(h.handle(req))
    assert rec.rag_called_with is None  # RAG 미호출
    assert resp.reply == "비 오는 오후"  # 계획 경로 결과


def test_gap_filters_out_too_long_activities():
    # gap=30분이면 60분짜리 북카페는 빠지고 10분짜리 스트레칭만 남는다
    h = RecommendHandler(_FakePlaceFinder(), _FakeRecommender(), 1500, 5)
    req = MessageRequest(
        text="뭐하지", lat=37.5, lng=127.0,
        schedule_context=ScheduleContext(gap_minutes=30),
    )
    resp = asyncio.run(h.handle(req))
    assert len(resp.todos) == 1
    assert resp.todos[0].estimated_minutes == 10


def test_gap_keeps_all_when_none():
    # scheduleContext 없으면 필터 안 함 — 둘 다 유지
    resp = _handle(_FakePlaceFinder())
    assert len(resp.todos) == 2


def test_gap_falls_back_when_all_too_long():
    # gap이 모든 활동보다 짧으면(전부 초과) 빈 추천 대신 원본 유지
    h = RecommendHandler(_FakePlaceFinder(), _FakeRecommender(), 1500, 5)
    req = MessageRequest(
        text="뭐하지", lat=37.5, lng=127.0,
        schedule_context=ScheduleContext(gap_minutes=5),
    )
    resp = asyncio.run(h.handle(req))
    assert len(resp.todos) == 2  # 폴백
