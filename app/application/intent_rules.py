"""명백한 인텐트는 규칙으로 선분류 (LLM 부담↓, 신뢰성↑).

작은 모델 분류기가 자꾸 틀리는 '명백한 도메인 밖 작업 요청'(코딩/번역 등)을
규칙으로 먼저 chat 처리한다. 애매하면 None을 반환해 LLM 분류로 위임한다.
"""

from app.domain.models import Intent

# 도메인 밖 신호 (확실한 것만 — 장소/활동 추천 표현과 안 겹치게 좁게)
# ① 작업 수행 요청
# ② '추천'이 붙어도 장소·활동이 아닌 콘텐츠 추천 (레시피/가사 등)
_TASK_KEYWORDS = (
    # 작업 수행
    "코드", "코딩", "퀵소트", "정렬 알고리즘", "알고리즘", "함수",
    "디버그", "컴파일", "번역해", "번역 해", "영작", "요약해줘",
    # 도메인 밖 콘텐츠 (명백한 것만)
    "레시피", "조리법", "만드는 법", "가사",
)


def rule_intent(text: str) -> Intent | None:
    """규칙으로 확실히 판단되면 Intent, 아니면 None(→ LLM 분류)."""
    if any(k in text for k in _TASK_KEYWORDS):
        return "chat"
    return None
