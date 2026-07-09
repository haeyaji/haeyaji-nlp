# haeyaji-nlp

할일 추천 두뇌. **RAG(장소) + 로컬 LLM(Ollama)** 으로 오늘 할 일을 추천하는 FastAPI 서비스.

`haeyaji-be`(Spring)가 이 서비스를 호출한다. nlp는 **stateless** — 맥락(프로필·히스토리·좌표)은 be가 매 요청에 실어 보내고, 장소검색·지오코딩도 be의 카카오 프록시(`/api/places/*`)를 통한다. 즉 **nlp의 외부 의존은 Ollama뿐**(외부 시크릿 없음).

## 아키텍처 (헥사고날)

```
api/             presentation — REST 엔드포인트 (POST /api/message)
application/      라우터 + 핸들러 + 규칙 + port(인터페이스)
domain/           순수 모델 (Place, TodoItem, Action …)
infrastructure/   어댑터 — be(장소검색 프록시) / Ollama(LLM) / 로그
```

추천 파이프라인: `규칙(검색어 결정) → be /places(실제 장소) → 프롬프트 → Ollama → 구조화 JSON`

## 셋업

```bash
# 1) Ollama 설치 + 모델 (한국어 특화 EXAONE 3.5 7.8b)
brew install ollama            # mac
ollama serve &                 # 백그라운드 (또는 Ollama 앱 실행)
ollama pull exaone3.5:7.8b

# 2) 파이썬 환경
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3) 환경변수
cp .env.example .env
#   OLLAMA_MODEL=exaone3.5:7.8b     (기본, .env로 교체 가능)
#   BE_BASE_URL=http://localhost:8090   ← 장소검색·지오코딩은 be(Spring) 프록시 경유
#   (카카오 REST 키는 nlp가 아니라 be가 보유. nlp엔 외부 시크릿 없음)

# 4) 실행
uvicorn app.main:app --reload --port 8000
```

> **의존성**: 추천 응답 자체는 Ollama만 있으면 뜬다. 다만 **장소가 붙는 추천**을 보려면
> `haeyaji-be`(:8090)가 함께 떠 있어야 한다(카카오 프록시). be 없이도 nlp는 부팅되며,
> 장소검색은 빈 결과로 graceful 폴백한다.

## 호출 예시

```bash
curl -s -X POST http://localhost:8000/api/message \
  -H "Content-Type: application/json" \
  -d '{
    "text": "비 오는데 갈 만한 카페 추천",
    "lat": 37.4979,
    "lng": 127.0276,
    "weather": "비, 18도",
    "timeOfDay": "오후 2시",
    "weekday": "토요일"
  }' | python3 -m json.tool
```

- 단일 엔드포인트 `POST /api/message` 가 추천/정보/잡담/액션(일정)을 인텐트로 라우팅.
- 요청·응답은 camelCase (snake_case 입력도 허용). 응답: `{ intent, reply, todos, options, actions }`.
- 문서: http://localhost:8000/docs (Swagger UI 자동 생성)

## 모델 교체 / 파인튜닝

- 다른 모델: `.env`의 `OLLAMA_MODEL` 변경 (코드 수정 없음)
- 파인튜닝(미래): `finetune/README.md` 참고. 포트 `Recommender`는 유지되므로
  구현체만 교체하면 된다.
