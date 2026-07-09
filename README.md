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

## 동작

**인텐트 4종** (규칙+LLM 하이브리드 라우팅)
- `recommend` — 장소/할 일 추천 (plan 모드: LLM이 활동 계획 → 코드가 카카오 검색으로 실제 장소 부착 / RAG 모드: 검색어 확정 시 후보 주입 후 LLM 선택)
- `info` — 날씨·주변 정보 응답
- `chat` — 인사/잡담
- `action` — 일정 생성/공유 (규칙 파서가 감지). nlp는 구조화 `actions` 만 반환, **실제 일정 CRUD·공유는 be가 실행**

**포위망(점진 좁히기)** — 막연한 요청("오늘 뭐하지")은 바로 답하지 않고 한 단계 좁혀 되묻는다.
날씨로 프레이밍: 비/눈이면 "실내가 좋겠어요" + 야외 칩 제외, 맑으면 야외 포함. 최대 2회 뒤엔 무조건 추천.
선택지(`options`)는 fe가 버튼으로 렌더 → 클릭 텍스트가 다음 메시지로.

**도메인 가드** — 코드작성/번역/레시피 등 도메인 밖은 규칙으로 하드 거절(LLM leak 차단).
단 "코딩할 만한 **곳**"처럼 장소 문맥이면 거절하지 않고 추천으로(스터디카페 등),
"소풍가서 김치찌개 레시피"처럼 도메인밖+안이 섞이면 되는 부분(소풍→공원)을 살려 추천.

**검색 판단은 nlp, 실행은 be** — "무엇을 검색할지"(소풍→공원, 카테고리코드, 정렬)는 nlp 규칙(`query_mapper`),
실제 카카오 호출·키는 be. nlp는 stateless라 맥락/개인화 데이터는 be가 매 요청에 주입.

## 테스트

```bash
.venv/bin/python -m pytest -q            # 유닛 (규칙·라우터·어댑터, LLM 불필요)

# 시나리오 채점 (Ollama + be 필요): 버킷별 자동 판정 → eval/results.md
PYTHONPATH=. .venv/bin/python eval/run_eval.py         # 전체
PYTHONPATH=. .venv/bin/python eval/run_eval.py mt      # 멀티턴(인젝션/사회공학)
```

## 모델 교체 / 파인튜닝

- 다른 모델: `.env`의 `OLLAMA_MODEL` 변경 (코드 수정 없음)
- 파인튜닝(미래): `finetune/README.md` 참고. 포트 `Recommender`는 유지되므로
  구현체만 교체하면 된다.
