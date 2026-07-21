"""scheduleContext가 추천 프롬프트에 반영되는지 (요청1)."""

from app.domain.models import DayTodo, Place, ScheduleContext
from app.infrastructure.llm.prompt import build_messages, build_rag_messages


def _user_content(messages):
    return messages[-1]["content"]


def test_gap_injected_into_plan_prompt():
    sc = ScheduleContext(gap_minutes=90)
    msgs = build_messages(
        weather="맑음", mood="", time_of_day="", weekday="", schedule_context=sc
    )
    body = _user_content(msgs)
    assert "90분" in body
    assert "일정 상황" in body


def test_day_todos_and_next_at_injected():
    sc = ScheduleContext(
        next_todo_at="2026-07-16T14:00:00",
        gap_minutes=120,
        day_todos=[DayTodo(title="회의", start_time="14:00", end_time="15:00")],
    )
    body = _user_content(
        build_messages(weather="", mood="", time_of_day="", weekday="", schedule_context=sc)
    )
    assert "회의" in body and "14:00~15:00" in body
    assert "2026-07-16T14:00:00" in body


def test_no_schedule_context_no_block():
    body = _user_content(
        build_messages(weather="맑음", mood="", time_of_day="", weekday="")
    )
    assert "일정 상황" not in body


def test_empty_schedule_context_no_block():
    # 필드가 전부 비면 블록 자체를 넣지 않는다
    body = _user_content(
        build_messages(
            weather="맑음", mood="", time_of_day="", weekday="",
            schedule_context=ScheduleContext(),
        )
    )
    assert "일정 상황" not in body


def test_gap_injected_into_rag_prompt():
    sc = ScheduleContext(gap_minutes=45)
    places = [Place(name="A카페", category="카페", address="서울")]
    body = _user_content(
        build_rag_messages(
            weather="", mood="", time_of_day="", weekday="",
            places=places, schedule_context=sc,
        )
    )
    assert "45분" in body
