"""행위(일정 생성/공유) 요청을 규칙으로 파싱 (코드 결정론).

7.8b는 tool-calling·복합 파싱이 약하므로 시간·친구·행위동사는 정규식/키워드로 뽑는다.
활동(무엇을 할지)만 애매하면 추천 경로(LLM)에 위임한다.
create/share 동사가 전혀 없으면 None → 기존 인텐트 경로로.
"""

import re
from dataclasses import dataclass

from app.domain.models import TimeRange

# ── 시간 ──────────────────────────────────────────────
_MERIDIEM = {"오전": "am", "아침": "am", "새벽": "am", "오후": "pm", "저녁": "pm", "밤": "pm", "낮": "pm"}
_HOUR_RE = re.compile(r"(오전|오후|저녁|밤|새벽|낮|아침)?\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분|\s*(반))?")


def _hm(m: re.Match) -> tuple[int, int, str | None]:
    hour = int(m.group(2))
    if m.group(4):        # "반"
        minute = 30
    elif m.group(3):      # "N분"
        minute = int(m.group(3))
    else:
        minute = 0
    mer = _MERIDIEM.get(m.group(1)) if m.group(1) else None
    return hour, minute, mer


def parse_time_range(text: str) -> TimeRange | None:
    """텍스트에서 시간 범위 추출. 시각 2개면 범위, 1개면 포인트(end=None), 없으면 None."""
    ms = list(_HOUR_RE.finditer(text))
    if not ms:
        return None
    sh, sm, mer = _hm(ms[0])
    eh = em = None
    if len(ms) >= 2:
        eh, em, _ = _hm(ms[1])
    raw = text[ms[0].start():ms[-1].end()].strip()
    return TimeRange(
        start_hour=sh, start_minute=sm,
        end_hour=eh, end_minute=(em or 0),
        meridiem=mer, raw=raw,
    )


# ── 공유 대상 ──────────────────────────────────────────
# "철수랑 공유", "영희한테 공유" → 이름 / "친구랑 공유" → None(be가 피커)
_FRIEND_RE = re.compile(r"([가-힣A-Za-z]{1,10})(?:랑|이랑|하고|한테|에게|와|과)[^.]{0,10}?(?:공유|보내|알려)")
_GENERIC_TARGET = ("친구", "친구들", "우리", "다같이", "다 같이", "모두")


def parse_target_friend(text: str) -> str | None:
    """공유 대상 이름. 없거나 '친구'처럼 일반이면 None → be가 친구 피커."""
    m = _FRIEND_RE.search(text)
    if not m:
        return None
    name = m.group(1).strip()
    return None if name in _GENERIC_TARGET else name


# ── 행위 동사 ──────────────────────────────────────────
_SCHED_WORDS = ("일정", "스케줄", "캘린더", "약속")
_CREATE_VERBS = ("생성", "만들", "추가", "등록", "잡아", "잡을", "넣어")


def _has_create(text: str) -> bool:
    return any(w in text for w in _SCHED_WORDS) and any(v in text for v in _CREATE_VERBS)


def _has_share(text: str) -> bool:
    return "공유" in text


@dataclass
class ActionParse:
    """규칙 파싱 결과 — 어떤 행위(생성/공유)와 어떤 슬롯이 잡혔는지."""

    create: bool
    share: bool
    time_range: TimeRange | None
    target_friend: str | None


def parse_action(text: str) -> ActionParse | None:
    """일정 생성/공유 요청이면 파싱 결과, 아니면 None(기존 경로).

    취소·추천만 있는 문장(요구 4 '1시 취소됐는데 추천')은 생성/공유 동사가 없어 None.
    """
    create = _has_create(text)
    share = _has_share(text)
    if not (create or share):
        return None
    return ActionParse(
        create=create,
        share=share,
        time_range=parse_time_range(text),
        target_friend=parse_target_friend(text) if share else None,
    )
