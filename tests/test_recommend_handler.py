import asyncio

from app.api.schemas import MessageRequest
from app.application.handler.recommend_handler import RecommendHandler
from app.domain.models import Place, PlannedTodo, RecommendationPlan


class _FakeRecommender:
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


class _FakeLogger:
    def log(self, **kwargs):
        pass


def _handle(place_finder):
    h = RecommendHandler(place_finder, _FakeRecommender(), _FakeLogger(), 1500, 5)
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
