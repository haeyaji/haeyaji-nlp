import json
from datetime import datetime, timezone
from pathlib import Path

from app.domain.models import Place, TodoRecommendation


class InteractionLogger:
    """추천 1건을 JSONL로 적재. 나중에 파인튜닝 학습셋의 원천 데이터가 된다.

    형식을 지금부터 학습 가능하게 맞춰두면 나중에 prepare_data 단계가 공짜.
    """

    def __init__(self, log_dir: str):
        self._dir = Path(log_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "interactions.jsonl"

    def log(
        self,
        *,
        request: dict,
        places: list[Place],
        result: TodoRecommendation,
    ) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "input": request,
            "candidates": [p.model_dump() for p in places],
            "output": result.model_dump(),
            "feedback": None,  # 나중에 사용자 '좋아요/별로'로 채움 → DPO 가능
        }
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
