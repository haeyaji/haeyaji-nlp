"""좁히기 선택지(칩) 생성 — 코드 규칙(결정론적), LLM 아님.

막연한 추천 요청일 때 fe가 버튼으로 보여줄 선택지를 만든다.
매번 같은 상황이면 같은 칩이 나와야 하므로(일관성·속도) 규칙으로 고정한다.
칩 텍스트는 클릭 시 그대로 사용자 메시지로 전송되므로,
분류기가 잘 알아듣는 표현(장소종류/분위기)으로 구성한다.
"""

_RAINY = ("비", "눈", "소나기", "장마")
_NIGHT = ("밤", "저녁", "새벽")

# 기본 칩 (낮·맑음 기준)
_BASE = ["맛집", "조용한 카페", "놀 거리", "야외/산책", "문화/전시", "휴식/힐링"]


def pick_options(weather: str = "", time_of_day: str = "") -> list[str]:
    """날씨·시간대에 맞는 좁히기 선택지 목록 (5~6개)."""
    options = list(_BASE)

    # 비/눈 → 야외 계열 제거, 실내 대안 보강
    if any(w in weather for w in _RAINY):
        options.remove("야외/산책")
        options.append("영화")

    # 밤/저녁/새벽 → 야외 산책 대신 술집·야식 계열
    if any(t in time_of_day for t in _NIGHT):
        if "야외/산책" in options:
            options.remove("야외/산책")
        options.append("술집/야식")

    return options[:6]
