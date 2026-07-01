"""자유 텍스트에서 지역/장소 후보 추출 (규칙 기반).

"강남역 가는데", "판교 갈건데" 같은 언급을 잡아 검색 중심을 바꾼다.
LLM 없이 규칙으로 후보만 뽑고, 실제 존재 여부는 지오코딩(카카오)에 위임한다.
(카카오가 좌표를 못 주면 그 후보는 버려지므로, 느슨한 규칙이어도 안전)
"""

import re

# 장소로 보기 어려운 흔한 단어 (오탐 방지)
_STOP = {
    "집", "여기", "거기", "저기", "어디", "우리", "밖", "안", "동네",
    "지역", "구역", "영역", "권역",
}

# ① '역'으로 끝나는 토큰 (강남역, 판교역, 서울역)
_SUFFIX = re.compile(r"[가-힣A-Za-z0-9]{1,}역")

# ② 이동/위치 표현 앞의 토큰 (판교 가는데, 홍대 근처, 여의도 쪽)
_BEFORE = re.compile(
    r"([가-힣A-Za-z0-9]{2,})\s*(?:가는데|갈건데|가려|가고|근처|쪽|앞|에서)"
)

# 후보 끝에 붙은 조사 제거 (집에→집). '로/으로'는 종로·을지로 등과 겹쳐 제외.
_PARTICLE = re.compile(r"(?:에서|에)$")


def extract_location_candidates(text: str) -> list[str]:
    """텍스트에서 지역 후보를 순서대로 반환 (조사 제거·중복·불용어 제거)."""
    raw: list[str] = [m.group(0) for m in _SUFFIX.finditer(text)]
    raw += [m.group(1) for m in _BEFORE.finditer(text)]

    seen: set[str] = set()
    out: list[str] = []
    for c in raw:
        c = _PARTICLE.sub("", c).strip()
        if len(c) >= 2 and c not in seen and c not in _STOP:
            seen.add(c)
            out.append(c)
    return out
