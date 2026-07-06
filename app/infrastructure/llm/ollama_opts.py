"""Ollama 호출 공통 옵션 — 속도 튜닝을 한곳에서 관리.

- keep_alive: 모델을 메모리에 유지해 매 요청 리로드(~6s) 방지
- num_ctx: 우리 프롬프트는 32k까지 필요 없음 → 낮춰 prefill·메모리 절약
- num_predict: 출력 상한(런어웨이 방지). 스키마 JSON이 잘리면 파싱 실패하므로 여유 있게.
"""

# 모델 상시 warm 유지 (Ollama 기본 5분 → 30분). 첫 응답 리로드 스파이크 제거.
KEEP_ALIVE = "30m"

# 컨텍스트 길이 (기본 32768). RAG 후보+few-shot 다 합쳐도 4k면 충분.
_NUM_CTX = 4096


def opts(temperature: float, num_predict: int | None = None) -> dict:
    o: dict = {"temperature": temperature, "num_ctx": _NUM_CTX}
    if num_predict is not None:
        o["num_predict"] = num_predict
    return o
