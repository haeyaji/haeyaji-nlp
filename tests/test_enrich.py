from app.domain.models import Place
from app.infrastructure.llm.ollama_recommender import (
    OllamaRecommender,
    _DraftRecommendation,
    _DraftTodo,
)


def _places() -> list[Place]:
    return [
        Place(
            name="그레이스케일커피",
            category="카페",
            address="서울 강남구",
            url="http://place.map.kakao.com/1",
            x=127.0,
            y=37.5,
            distance_m=100,
        )
    ]


def _draft(place_name):
    return _DraftRecommendation(
        analysis="a",
        todos=[
            _DraftTodo(
                title="t", reason="r", category="휴식",
                estimated_minutes=30, place_name=place_name,
            )
        ],
    )


def test_enrich_fills_coords_from_real_place():
    rec = OllamaRecommender._enrich(_draft("그레이스케일커피"), _places())
    t = rec.todos[0]
    assert (t.x, t.y, t.distance_m) == (127.0, 37.5, 100)
    assert t.place_url == "http://place.map.kakao.com/1"


def test_enrich_nulls_hallucinated_place():
    # 후보에 없는 장소명 → 환각으로 보고 연결 해제
    rec = OllamaRecommender._enrich(_draft("존재하지않는카페"), _places())
    assert rec.todos[0].place_name is None
    assert rec.todos[0].x is None


def test_enrich_placeless_todo_ok():
    rec = OllamaRecommender._enrich(_draft(None), _places())
    assert rec.todos[0].place_name is None
    assert rec.todos[0].x is None
