import asyncio

from app.api.schemas import MessageRequest, MessageResponse
from app.application.action_rules import parse_action
from app.application.handler.action_handler import ActionHandler
from app.domain.models import TodoItem


class _FakeRecommend:
    """recommend 핸들러 대역 — 넘어온 req 캡처 + 정해둔 todos 반환."""

    def __init__(self, todos=None):
        self._todos = todos or []
        self.seen: MessageRequest | None = None

    async def handle(self, req: MessageRequest) -> MessageResponse:
        self.seen = req
        return MessageResponse(intent="recommend", reply="추천", todos=self._todos)


def _place_todo():
    return TodoItem(
        title="스타벅스에서 작업", reason="r", category="CAFE_DESSERT",
        estimated_minutes=60, place_name="스타벅스 강남점", place_url="http://x",
    )


def _run(text, todos=None):
    fake = _FakeRecommend(todos)
    resp = asyncio.run(
        ActionHandler(recommend_handler=fake).handle(
            MessageRequest(text=text, lat=37.5, lng=127.0), parse_action(text)
        )
    )
    return resp, fake


def test_explicit_activity_full_create():
    resp, fake = _run("1시부터 3시까지 카페 일정 만들어줘", todos=[_place_todo()])
    assert resp.intent == "action"
    assert fake.seen.search_keywords == ["카페"]        # 활동 명시 → 장소 검색
    assert len(resp.actions) == 1
    a = resp.actions[0]
    assert a.type == "schedule.create"
    assert (a.time_range.start_hour, a.time_range.end_hour) == (1, 3)
    assert a.place_name == "스타벅스 강남점"


def test_compound_create_and_share():
    resp, _ = _run("1시부터 3시까지 카페 일정 만들고 친구랑 공유해줘", todos=[_place_todo()])
    types = [a.type for a in resp.actions]
    assert types == ["schedule.create", "schedule.share"]
    share = resp.actions[1]
    assert share.ref == "$lastCreated"      # 방금 만든 일정 참조
    assert share.target_friend is None      # '친구' = 일반 → be 피커


def test_share_only_with_name():
    resp, _ = _run("이 일정 철수랑 공유해줘")
    assert [a.type for a in resp.actions] == ["schedule.share"]
    assert resp.actions[0].target_friend == "철수"
    assert resp.actions[0].ref is None      # 생성 없음 → 참조 없음


def test_vague_activity_recommends_only():
    # 활동 모호 → Mode A: 완전 액션 없이 추천만, 사용자가 고르면 be가 생성
    resp, fake = _run("1시부터 3시까지 일정 만들어줘", todos=[_place_todo()])
    assert fake.seen.search_keywords == []   # 검색어 강제 안 함
    assert resp.actions == []
    assert resp.todos                        # 추천은 제공
