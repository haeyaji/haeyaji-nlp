"""시스템 프롬프트 + few-shot + 대화 히스토리 + 사용자 메시지 구성.

작은(7B급) 모델일수록 프롬프트가 중요하므로:
- 명시적 원칙/금지 규칙
- few-shot 예시
- '목록에 없는 장소는 지어내지 마' (환각 차단)
- 최근 대화 히스토리 주입 (후속 질문 대응)
"""

from app.domain.models import Place, Turn, UserProfile

# 작은 모델 품질을 위해 최근 N턴만 사용
MAX_HISTORY_TURNS = 6


def _history_messages(history: list[Turn] | None) -> list[dict]:
    """대화 히스토리를 실제 메시지 턴으로 변환 (최근 N턴). 없으면 빈 리스트."""
    if not history:
        return []
    return [{"role": t.role, "content": t.content} for t in history[-MAX_HISTORY_TURNS:]]


SYSTEM = """너는 사용자의 오늘 컨디션을 보고 할 일을 추천하는 비서다.

[추천 원칙]
1. 날씨·기분·위치·시간대·요일을 모두 근거로 삼는다.
2. 기분이 가라앉아 있으면 부담 적은 일(5~15분)부터 제안한다. 활기차면 도전적인 일을 섞는다.
3. 시간대를 고려한다: 늦은 밤엔 수면을 방해하는 격한 활동 금지.

[장소 사용 규칙 - 매우 중요]
- 아래 '주변 실제 장소 목록'에 있는 장소만 추천에 사용한다.
- 목록에 없는 장소 이름은 절대 지어내지 마라.
- 장소가 필요 없는 할 일(집에서 하는 일 등)은 place_name을 비워둔다.

[금지]
- 날씨와 모순되는 추천 금지 (비 오는 날 등산/소풍 등).
- 막연한 추천 금지 ("운동하기" X → "집에서 10분 스트레칭" O).
- 같은 카테고리만 3개 이상 몰아주기 금지.

[대화 맥락]
- 직전 대화가 있으면 참고한다. "다른 데 추천"이면 이전에 추천한 것과 겹치지 않게 고른다.

[작업 순서]
먼저 analysis에 상황을 한 문장으로 분석한 뒤, 그 분석에 맞는 할 일 3~5개를 고른다.
모든 출력은 자연스러운 한국어로만 작성한다. 한자나 다른 언어(중국어 등)를 절대 섞지 마라."""

_FEWSHOT_USER = """날씨: 맑음, 22도
기분: 활기참
위치 시간대: 오전 10시
요일: 토요일

[주변 실제 장소 목록]
- 한강시민공원 (공원, 서울 영등포구 여의동로 330)
- 스타벅스 여의도점 (카페, 서울 영등포구 국제금융로 10)"""

_FEWSHOT_ASSISTANT = (
    '{"analysis":"맑은 주말 오전에 기분도 좋음 — 외부 활동과 생산적인 일을 섞기 좋다.",'
    '"todos":['
    '{"title":"한강시민공원에서 자전거 타기","reason":"맑은 날씨+활기참, 주말 오전에 최적",'
    '"category":"야외","estimated_minutes":60,"place_name":"한강시민공원","place_url":null},'
    '{"title":"밀린 방 청소하기","reason":"에너지 높을 때 미뤄둔 일 처리하기 좋음",'
    '"category":"생산성","estimated_minutes":40,"place_name":null,"place_url":null}'
    "]}"
)


def _format_profile(profile: UserProfile | None) -> str:
    """사용자 프로필을 프롬프트 블록으로. 없거나 비면 빈 문자열(주입 안 함)."""
    if profile is None:
        return ""
    parts: list[str] = []
    if profile.preferred_categories:
        parts.append(f"선호 카테고리: {', '.join(profile.preferred_categories)}")
    if profile.vibe:
        parts.append(f"선호 분위기: {profile.vibe}")
    if profile.intensity:
        parts.append(f"활동 강도 선호: {profile.intensity}")
    if profile.avoid:
        parts.append(f"회피: {', '.join(profile.avoid)}")
    if profile.recent_selections:
        parts.append(f"최근 선택: {', '.join(profile.recent_selections)}")
    if not parts:
        return ""
    body = "\n".join(f"- {p}" for p in parts)
    return f"[사용자 프로필 — 추천에 반영하되 특정 장소 단정은 금지]\n{body}\n\n"


def _format_places(places: list[Place]) -> str:
    if not places:
        return "(주변 장소 없음 — 집/실내에서 할 수 있는 일 위주로 추천)"
    lines = []
    for p in places:
        dist = f", {p.distance_m}m" if p.distance_m is not None else ""
        lines.append(f"- {p.name} ({p.category}, {p.address}{dist})")
    return "\n".join(lines)


def build_messages(
    *,
    weather: str,
    mood: str,
    time_of_day: str,
    weekday: str,
    places: list[Place],
    note: str = "",
    user_profile: UserProfile | None = None,
    history: list[Turn] | None = None,
) -> list[dict]:
    # 사용자가 직접 말한 요청("비 맞고 싶어" 등)이 있으면 최우선 반영
    note_line = f"사용자 요청(최우선 반영, 단 안전은 챙김): {note}\n" if note else ""
    user = (
        f"{note_line}"
        f"{_format_profile(user_profile)}"
        f"날씨: {weather}\n"
        f"기분: {mood}\n"
        f"시간대: {time_of_day}\n"
        f"요일: {weekday}\n\n"
        f"[주변 실제 장소 목록]\n{_format_places(places)}"
    )
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": _FEWSHOT_USER},
        {"role": "assistant", "content": _FEWSHOT_ASSISTANT},
        *_history_messages(history),
        {"role": "user", "content": user},
    ]


# ─────────────────────────────────────────────────────────────
# 인텐트 분류 / 정보 / 잡담 프롬프트
# ─────────────────────────────────────────────────────────────

_CLASSIFY_SYSTEM = """사용자 메시지의 의도를 recommend / info / chat 중 하나로 분류한다.

먼저 '작업 수행 요청'인지 본다:
- chat: 인사·감사·자기소개 등 잡담, 그리고 추천/정보와 무관하게 '작업을 시키는' 요청
  (코딩·정렬·번역·계산·글쓰기·요약·전문상담 등). "~짜줘/만들어줘/번역해줘/계산해줘/써줘"는 chat.
작업 요청이 아니면:
- recommend: "어디 가서 무엇을 할지"(장소·활동) 추천 요청.
  맛집·카페·공원·전시 등 갈 곳, 또는 산책·운동 같은 활동. "갈 데/가고싶어/뭐하지/심심" 등.
- info: 특정 사실을 묻는 질문. "어때?/있어?/몇 시?/사람 많아?/영업해?".

[중요] "추천"이 들어가도 대상이 장소·활동이 아니면 chat이다.
  레시피·요리법, 노래·음악, 영화/드라마 작품, 책 내용, 선물, 옷 코디 등의 추천은 chat(도메인 밖).
  (예: "맛집 추천"=recommend, "레시피 추천"=chat, "노래 추천"=chat)

직전 대화가 있으면 후속 질문도 맥락으로 분류한다.
  (예: 직전에 장소를 추천했고 "왜 그거 추천했어?"면 info, "다른 데"면 recommend)

recommend와 info 사이가 애매하면 recommend(주 기능). 작업 요청·도메인 밖 추천은 chat.
intent 하나만 JSON으로 답한다."""

# few-shot — 작은 모델 분류 안정화
_CLASSIFY_FEWSHOT: list[tuple[str, str]] = [
    ("비 오는데 조용한 데 가고싶어", "recommend"),
    ("심심한데 뭐하지", "recommend"),
    ("강남역 맛집 추천해줘", "recommend"),
    ("김치찌개 레시피 추천해줘", "chat"),
    ("노래 추천해줘", "chat"),
    ("영화 추천해줘", "chat"),
    ("오늘 날씨 어때?", "info"),
    ("근처 카페 사람 많아?", "info"),
    ("안녕! 너 누구야?", "chat"),
    ("파이썬으로 정렬 코드 짜줘", "chat"),
]

_INFO_SYSTEM = """너는 할 일 추천 비서다. 사용자의 정보 질문에 답한다.

[규칙]
- 아래 제공된 맥락(날씨, 주변 장소)과 직전 대화에 있는 정보로만 답한다.
- "왜 그걸 추천했어?" 같은 후속 질문은 직전 추천의 이유를 근거로 설명한다.
- 실시간 정보(지금 사람 수/혼잡도, 영업중 여부, 실시간 가격 등)는 알 수 없다.
  지어내지 말고 "실시간 정보는 제공하지 않아요"라고 솔직히 답해라.
- 짧고 친절하게. 자연스러운 한국어로만 답하고 한자/외국어를 섞지 마라."""

_CHAT_SYSTEM = """너는 '오늘 갈 만한 곳·할 일'을 추천하는 비서다. 다음 규칙을 반드시 지켜라.

1) 인사·감사·자기소개 같은 가벼운 잡담 → 1문장으로 친근하게 답한다.
2) 장소·활동 추천이 아닌 모든 요청(코딩·번역·계산·레시피·노래·영화 작품·책·선물·전문상담 등)
   → 절대 들어주지 마라. 그 내용을 한 글자도 제시하지 말고, "어떤 거 좋아하세요?"처럼 되묻지도 마라.
   딱 이 문장만 답한다:
   "그건 도와드리기 어려워요. 저는 오늘 갈 만한 곳이나 할 일을 추천해드려요. 어떤 활동을 찾으세요?"

자연스러운 한국어로만 답하고, 한자/외국어를 섞지 마라."""


def build_classify_messages(text: str, history: list[Turn] | None = None) -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": _CLASSIFY_SYSTEM}]
    for ex_text, ex_intent in _CLASSIFY_FEWSHOT:
        msgs.append({"role": "user", "content": ex_text})
        msgs.append({"role": "assistant", "content": f'{{"intent": "{ex_intent}"}}'})
    msgs.extend(_history_messages(history))
    msgs.append({"role": "user", "content": text})
    return msgs


def build_info_messages(
    *,
    text: str,
    weather: str,
    places: list[Place],
    history: list[Turn] | None = None,
) -> list[dict]:
    ctx = (
        f"[제공된 맥락]\n"
        f"- 현재 날씨: {weather or '정보 없음'}\n"
        f"- 주변 장소:\n{_format_places(places)}"
    )
    return [
        {"role": "system", "content": _INFO_SYSTEM},
        *_history_messages(history),
        {"role": "user", "content": f"{ctx}\n\n[질문]\n{text}"},
    ]


def build_chat_messages(text: str, history: list[Turn] | None = None) -> list[dict]:
    return [
        {"role": "system", "content": _CHAT_SYSTEM},
        *_history_messages(history),
        {"role": "user", "content": text},
    ]
