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


def _format_places(places: list[Place]) -> str:
    """정보(info) 응답 맥락용 장소 목록 포맷."""
    if not places:
        return "(주변 장소 정보 없음)"
    lines = []
    for p in places:
        dist = f", {p.distance_m}m" if p.distance_m is not None else ""
        lines.append(f"- {p.name} ({p.category}, {p.address}{dist})")
    return "\n".join(lines)


def _history_messages(history: list[Turn] | None) -> list[dict]:
    """대화 히스토리를 실제 메시지 턴으로 변환 (최근 N턴). 없으면 빈 리스트."""
    if not history:
        return []
    return [{"role": t.role, "content": t.content} for t in history[-MAX_HISTORY_TURNS:]]


SYSTEM = """너는 사용자의 오늘 컨디션(날씨·기분·시간대·요일·위치)을 보고
'오늘 뭐 하면 좋을지'를 구체적인 할 일로 추천하는 비서다.

[핵심 방식 - 매우 중요]
- 너는 '무엇을 할지'(활동)와 '어떤 곳을 찾을지'(검색어)만 정한다.
- 실제 가게 이름/좌표는 시스템이 카카오 지도에서 찾아 채운다.
  그러니 특정 가게 이름을 절대 지어내지 마라. 대신 search_query에 '검색할 장소 종류'를 적어라.
- search_query는 카카오 지도에서 바로 검색되는 '장소 종류'를 수식어 없이 짧게(보통 한 단어) 적는다.
  좋은 예: "북카페", "라멘", "전시회", "클라이밍장", "PC방", "맛집"
  나쁜 예: "스타벅스 강남점"(특정 상호), "현지 맛집"·"분위기 좋은 카페"·"가까운 밥집"(수식어 금지)
- 집/온라인 등 장소가 필요 없는 일만 search_query를 null로 둔다.

[추천 원칙]
1. 이 앱은 '나가서 갈 만한 곳' 추천이 핵심이다. 되도록 장소 기반 활동으로 제안하고 search_query를 채워라.
   집/온라인에서 하는 일은 전체에서 최대 1개까지만.
2. 날씨·기분·시간대·요일을 근거로 삼는다.
   - 비/눈이면 실내 위주(등산/소풍 금지). 늦은 밤엔 수면 방해하는 격한 활동 금지.
   - 무기력/피곤해도 '부담 적게 갈 수 있는 곳'(가까운 카페 등)을 우선 제안한다.
   - 활기차면 활동적인 곳을 섞는다.
3. 서로 다른 카테고리로 3~5개를 다양하게 제안한다(같은 종류 몰빵 금지).
   단, [사용자 지정 종류]가 주어지면 반대로 모든 할 일을 그 종류로만 구성한다
   (다양성은 그 종류 안에서 — 예: 한식이면 국밥/고기/찌개처럼).
4. 사용자가 특정 활동/장소종류를 콕 집으면(예: "PC방", "밥집") 그걸 최우선으로 반영한다.

[대화 맥락]
- 직전 대화가 있으면 참고한다. "다른 거"면 이전과 겹치지 않게 고른다.

먼저 analysis에 상황을 한 문장으로 분석한 뒤, 그에 맞는 할 일 3~5개를 만든다.
각 할 일: title(구체적 활동), reason(왜 지금), category, estimated_minutes, search_query(검색어 또는 null).
모든 출력은 자연스러운 한국어로만. 한자/외국어를 절대 섞지 마라."""

_FEWSHOT_USER = """날씨: 비, 18도
기분: 무기력
시간대: 오후 3시
요일: 토요일"""

_FEWSHOT_ASSISTANT = (
    '{"analysis":"비 오고 기분도 처지는 주말 오후 — 부담 적은 실내 활동 위주가 좋다.",'
    '"todos":['
    '{"title":"근처 북카페에서 책 읽기","reason":"비 오는 날 조용히 재충전하기 좋음",'
    '"category":"휴식","estimated_minutes":60,"search_query":"북카페"},'
    '{"title":"가까운 전시 관람하기","reason":"실내에서 기분을 환기하기 좋음",'
    '"category":"실내","estimated_minutes":90,"search_query":"전시회"},'
    '{"title":"집에서 10분 스트레칭","reason":"무기력할 땐 가벼운 몸풀기부터",'
    '"category":"휴식","estimated_minutes":10,"search_query":null}'
    "]}"
)

# 두 번째 예시 — 야외/활동적 활동도 search_query를 채우는 걸 보여줌
_FEWSHOT2_USER = """날씨: 맑음, 23도
기분: 활기참
시간대: 오전 11시
요일: 일요일"""

_FEWSHOT2_ASSISTANT = (
    '{"analysis":"맑고 활기찬 주말 오전 — 나가서 활동적으로 보내기 좋다.",'
    '"todos":['
    '{"title":"공원에서 산책하기","reason":"맑은 날 야외 활동에 최적",'
    '"category":"야외","estimated_minutes":40,"search_query":"공원"},'
    '{"title":"근처에서 브런치 먹기","reason":"활기찬 기분에 맛있는 식사 곁들이기",'
    '"category":"맛집/카페","estimated_minutes":60,"search_query":"브런치"},'
    '{"title":"자전거 타기","reason":"넘치는 에너지를 발산하기 좋음",'
    '"category":"야외","estimated_minutes":60,"search_query":"자전거대여"}'
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


def build_messages(
    *,
    weather: str,
    mood: str,
    time_of_day: str,
    weekday: str,
    note: str = "",
    focus: str = "",
    user_profile: UserProfile | None = None,
    history: list[Turn] | None = None,
) -> list[dict]:
    # 사용자가 직접 말한 요청("PC방 가고싶어" 등)이 있으면 최우선 반영
    note_line = f"사용자 요청(최우선 반영, 단 안전은 챙김): {note}\n" if note else ""
    # 좁히기로 확정된 종류가 있으면 몰빵 지시 (카페 등 다른 종류 섞임 방지)
    focus_line = (
        f"[사용자 지정 종류 — 반드시 준수] {focus} — 모든 할 일(title)과 "
        f"search_query를 이 종류 관련으로만 구성한다.\n"
        if focus
        else ""
    )
    user = (
        f"{note_line}"
        f"{focus_line}"
        f"{_format_profile(user_profile)}"
        f"날씨: {weather or '정보 없음'}\n"
        f"기분: {mood or '정보 없음'}\n"
        f"시간대: {time_of_day or '정보 없음'}\n"
        f"요일: {weekday or '정보 없음'}"
    )
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": _FEWSHOT_USER},
        {"role": "assistant", "content": _FEWSHOT_ASSISTANT},
        {"role": "user", "content": _FEWSHOT2_USER},
        {"role": "assistant", "content": _FEWSHOT2_ASSISTANT},
        *_history_messages(history),
        {"role": "user", "content": user},
    ]


# ─────────────────────────────────────────────────────────────
# 인텐트 분류 / 정보 / 잡담 프롬프트
# ─────────────────────────────────────────────────────────────

_CLASSIFY_SYSTEM = """사용자 메시지를 분석해 intent와 keywords를 JSON으로 답한다.

[intent] recommend / info / chat 중 하나:
- chat: 인사·감사·자기소개 등 잡담, 그리고 추천/정보와 무관하게 '작업을 시키는' 요청
  (코딩·정렬·번역·계산·글쓰기·요약·전문상담 등). "~짜줘/만들어줘/번역해줘/계산해줘/써줘"는 chat.
- recommend: "어디 가서 무엇을 할지"(장소·활동) 추천 요청.
  맛집·카페·공원·전시 등 갈 곳, 또는 산책·운동 같은 활동. "갈 데/가고싶어/뭐하지/심심" 등.
- info: 특정 사실을 묻는 질문. "어때?/있어?/몇 시?/사람 많아?/영업해?".

[중요] "추천"이 들어가도 대상이 장소·활동이 아니면 chat이다.
  레시피·요리법, 노래·음악, 영화/드라마 작품, 책 내용, 선물, 옷 코디 등의 추천은 chat(도메인 밖).
  (예: "맛집 추천"=recommend, "레시피 추천"=chat, "노래 추천"=chat)
직전 대화가 있으면 후속 질문도 맥락으로 분류한다.
recommend와 info 사이가 애매하면 recommend. 작업 요청·도메인 밖 추천은 chat.

[keywords — 무엇] 사용자가 찾는 '장소 종류/활동'을 카카오 지도 검색어 배열로 뽑는다.
- 그대로 검색 가능한 장소 명사로 정규화한다: 밥집/배고파→["맛집"], "피방/피시방/PC방"→["PC방"],
  "볼링"→["볼링장"], "당구"→["당구장"], "책 읽을 데"→["북카페","도서관"], "술 한잔"→["술집"].
- 여러 개면 여러 개. 특정 장소 종류를 안 밝히면(그냥 "심심"/"뭐하지"/"놀 데") [] 로 둔다(날씨·기분으로 자동 추천).
- 지역명(강남역/판교 등)은 keywords에 넣지 않는다(그건 위치임).
- intent가 recommend가 아니면 keywords는 [].

[prefer — 필터] 어떤 곳을 우선할지.
- "유명한/핫한/인기/소문난/맛집으로 유명" → "famous"
- "가까운/근처/걸어서 갈/바로 옆" → "near"
- 언급 없으면 null.

[vague/question/options — 점진 좁히기] 좋은 추천을 하기에 카테고리 정보가 부족하면
vague=true로 두고, 한 단계만 좁히는 질문(question)과 버튼 선택지(options)를 만든다.
- 넓은 요청("뭐하지","추천해줘") → 큰 갈래를 묻는다: ["먹으러 가기","카페","놀거리","휴식","문화생활"]
- 큰 갈래는 잡혔지만 넓을 때("먹으러 가기","밥 먹을 데") → 세부를 묻는다: ["한식","중식","일식","양식","분식","고기"]
- 충분히 구체적이면("한식","PC방","조용한 카페") vague=false, question="", options=[].
- options는 2~6개, 각각 그대로 검색/분류 가능한 짧은 한국어 명사.
- 직전 대화에서 이미 두 번 좁혔으면 더 묻지 말고 vague=false로 추천을 진행한다.
- intent가 recommend가 아니면 vague=false, question="", options=[].
JSON만 답한다."""

# few-shot — (텍스트, intent, keywords, prefer, vague, question, options)
_CLASSIFY_FEWSHOT: list[tuple[str, str, list[str], str | None, bool, str, list[str]]] = [
    ("그냥 추천해줘", "recommend", [], None, True,
     "뭐가 당기세요?", ["먹으러 가기", "카페", "놀거리", "휴식", "문화생활"]),
    ("오늘 뭐하지", "recommend", [], None, True,
     "어떤 쪽이 끌리세요?", ["먹으러 가기", "카페", "놀거리", "휴식", "문화생활"]),
    ("먹으러 가기", "recommend", ["맛집"], None, True,
     "어떤 음식이 좋으세요?", ["한식", "중식", "일식", "양식", "분식", "고기"]),
    ("배고파 밥 먹을 데", "recommend", ["맛집"], None, True,
     "어떤 음식이 당기세요?", ["한식", "중식", "일식", "양식", "분식"]),
    ("한식", "recommend", ["한식"], None, False, "", []),
    ("비 오는데 조용한 데 가고싶어", "recommend", [], None, False, "", []),
    ("강남역 맛집 추천해줘", "recommend", ["맛집"], None, False, "", []),
    ("강남역 갈 건데 거기서 유명한 거 추천", "recommend", [], "famous", False, "", []),
    ("가까운 밥집 추천해줘", "recommend", ["맛집"], "near", False, "", []),
    ("홍대 방탈출 하고싶어", "recommend", ["방탈출카페"], None, False, "", []),
    ("PC방 가고싶다", "recommend", ["PC방"], None, False, "", []),
    ("볼링 치러 갈까", "recommend", ["볼링장"], None, False, "", []),
    ("김치찌개 레시피 추천해줘", "chat", [], None, False, "", []),
    ("노래 추천해줘", "chat", [], None, False, "", []),
    ("오늘 날씨 어때?", "info", [], None, False, "", []),
    ("안녕! 너 누구야?", "chat", [], None, False, "", []),
    ("파이썬으로 정렬 코드 짜줘", "chat", [], None, False, "", []),
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
    import json

    msgs: list[dict] = [{"role": "system", "content": _CLASSIFY_SYSTEM}]
    for ex_text, ex_intent, ex_kw, ex_prefer, ex_vague, ex_q, ex_opts in _CLASSIFY_FEWSHOT:
        msgs.append({"role": "user", "content": ex_text})
        answer = json.dumps(
            {
                "intent": ex_intent,
                "keywords": ex_kw,
                "prefer": ex_prefer,
                "vague": ex_vague,
                "question": ex_q,
                "options": ex_opts,
            },
            ensure_ascii=False,
        )
        msgs.append({"role": "assistant", "content": answer})
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
