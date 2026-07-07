# todo-nlp

할일 추천 두뇌. **RAG(카카오 장소) + 로컬 LLM(Ollama)** 으로 오늘 할 일을 추천하는 FastAPI 서비스.

`todo-be`(Spring)가 이 서비스를 호출한다. 모델·프롬프트·(미래)파인튜닝은 전부 여기 모여 있다.

## 아키텍처 (sapari-be식 레이어)

```
api/             presentation — REST 엔드포인트 (POST /api/recommend)
application/      유스케이스 조립 + 규칙 + port(인터페이스)
domain/           순수 모델 (Place, TodoItem, TodoRecommendation)
infrastructure/   어댑터 — 카카오(RAG) / Ollama(LLM) / 로그
```

추천 파이프라인: `규칙(검색어 결정) → 카카오(실제 장소) → 프롬프트 → Ollama → 구조화 JSON`

## 셋업

```bash
# 1) Ollama 설치 + 모델 (팀 통일: qwen2.5:3b)
brew install ollama        # mac
ollama serve &             # 백그라운드
ollama pull qwen2.5:3b

# 2) 파이썬 환경
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3) 환경변수
cp .env.example .env       # .env에 BE_BASE_URL 확인 (장소검색은 be 경유)

# 4) 실행
uvicorn app.main:app --reload --port 8000
```

## 호출 예시

```bash
curl -s -X POST http://localhost:8000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "weather": "비, 18도, 습함",
    "mood": "무기력",
    "lat": 37.4979,
    "lng": 127.0276,
    "time_of_day": "오후 2시",
    "weekday": "토요일"
  }' | python3 -m json.tool
```

문서: http://localhost:8000/docs (Swagger UI 자동 생성)

## 모델 교체 / 파인튜닝

- 다른 모델: `.env`의 `OLLAMA_MODEL` 변경 (코드 수정 없음)
- 파인튜닝(미래): `finetune/README.md` 참고. 포트 `Recommender`는 유지되므로
  구현체만 교체하면 된다.
