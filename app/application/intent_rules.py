"""명백한 인텐트는 규칙으로 선분류 (LLM 부담↓, 신뢰성↑).

작은(7B) 모델은 "거절해" 프롬프트를 잘 안 지켜서, 도메인 밖 요청·프롬프트 인젝션은
규칙으로 먼저 잡아 LLM을 아예 안 태우고 하드 거절한다(leak 원천차단).
애매하면 None을 반환해 LLM 분류로 위임한다.
"""

from typing import Literal

from app.domain.models import Intent

# ── 도메인 밖 신호 (장소/활동 추천과 안 겹치게) ────────────────────
# 작업 수행 요청 + 장소·활동이 아닌 콘텐츠 추천/생성
_OUT_OF_DOMAIN = (
    # 코딩/기술
    "코드", "코딩", "퀵소트", "알고리즘", "함수", "디버그", "컴파일",
    "시큐리티", "스프링", "자바", "파이썬", "리액트", "서버 설정",
    # 번역/계산/글쓰기
    "번역해", "번역 해", "영작", "영어로", "요약해", "계산해", "곱하기", "나누기",
    "이력서", "자기소개서", "이메일 써", "편지 써", "글 써줘", "작성해줘",
    # 창작
    "시 지어", "시 한 편", "소설", "작사", "작곡", "가사",
    # 요리 (레시피/조리)
    "레시피", "조리법", "만드는 법", "만드는법", "끓이는 법", "끓이는법",
    "끓이는", "볶는 법", "굽는 법", "요리법",
    # 콘텐츠 추천 (장소 아님)
    "노래 추천", "음악 추천", "영화 추천", "드라마 추천", "책 추천",
    "선물 추천", "코디 추천", "옷 추천",
    # 전문/상담/기타
    "주식", "투자", "코인", "부동산", "운세", "사주", "타로", "로또",
    "숙제", "문제 풀", "증명해", "작명", "이름 지어", "이름 지어줘",
    "상담", "고민 있", "어떡해", "어떻게 해야",
    "식단", "다이어트", "운동 루틴", "헬스 루틴",
)

# ── 프롬프트 인젝션 / 시스템 탈취 시도 ────────────────────────────
_INJECTION = (
    "프롬프트", "시스템 프롬프트", "system prompt",
    "너의 지침", "너의 규칙", "지침 알려", "규칙 알려", "설정 알려",
    "지시를 무시", "무시하고", "이전 지시", "위의 지시", "이전 대화 무시",
    "초기화", "리셋", "reset", "역할을 잊", "역할 무시",
    "기억하는 컨텍스트", "기억하고 있는", "받은 컨텍스트", "컨텍스트를 알려",
    "컨텍스트에 대해", "ignore previous", "ignore above", "you are now", "jailbreak",
)

# ── 인사/잡담 신호 (chat으로 친근히 응대해도 됨) ──────────────────
_GREETING = (
    "안녕", "하이", "헬로", "hi", "hello", "반가", "누구야", "누구세요",
    "뭐야 너", "넌 뭐", "이름이 뭐", "고마워", "감사", "잘 있었", "ㅎㅇ",
)

# ── 장소 문맥이면 오탐일 수 있는 '모호어' (도메인 밖 서브셋) ────────
# "코딩 해줘"(작업 요청, 도메인 밖) vs "코딩할 만한 곳"(장소 추천, 도메인 안)처럼
# 뒤에 장소 마커가 붙으면 추천 요청이므로 하드거절하면 안 된다.
_AMBIGUOUS_DOMAIN = ("코드", "코딩", "자바", "파이썬", "리액트", "코인")

# ── 장소 추천 문맥 신호 ("~할 만한 곳" 등) ────────────────────────
_PLACE_MARKERS = (
    "곳", "장소", "카페", "자리", "스팟",
    "할 만한", "하기 좋은", "갈 만한", "할만한", "갈만한", "가 볼", "갈 데", "할 데",
)

BlockReason = Literal["injection", "domain"]


def _domain_hits(text: str) -> list[str]:
    """텍스트에 걸린 도메인 밖 키워드들. '코인노래방'은 장소이므로 '코인' 오탐 제거."""
    hits = [k for k in _OUT_OF_DOMAIN if k in text]
    if "코인노래" in text:
        hits = [h for h in hits if h != "코인"]
    return hits


def _is_place_context(text: str) -> bool:
    """장소 추천 문맥('~할 만한 곳' 등) 신호가 있으면 True."""
    return any(m in text for m in _PLACE_MARKERS)


def _rescued(text: str, hits: list[str]) -> bool:
    """걸린 게 전부 모호어인데 장소 문맥이면 오탐 → 거절 해제 대상."""
    return bool(hits) and all(h in _AMBIGUOUS_DOMAIN for h in hits) and _is_place_context(text)


def blocked_reason(text: str) -> BlockReason | None:
    """하드 거절 대상이면 사유, 아니면 None. (LLM 안 태우고 즉시 거절용)

    장소 문맥('코딩할 만한 곳')에서 모호어(코딩/코인 등)만 걸린 경우는 오탐이므로
    거절하지 않는다. 순수 작업 요청('코딩 해줘')·명백한 도메인 밖만 거절.
    """
    low = text.lower()
    if any(k in text for k in _INJECTION) or any(k in low for k in _INJECTION):
        return "injection"
    hits = _domain_hits(text)
    if not hits or _rescued(text, hits):
        return None
    return "domain"


def is_greeting(text: str) -> bool:
    """인사/자기소개성 잡담이면 True (chat 핸들러에서 친근히 응대 허용)."""
    return any(k in text.lower() for k in _GREETING)


def rule_intent(text: str) -> Intent | None:
    """규칙으로 확실히 chat이면 'chat', 아니면 None(→ LLM 분류)."""
    if blocked_reason(text) is not None:
        return "chat"
    return None
