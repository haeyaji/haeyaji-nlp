import asyncio

from app.api.schemas import MessageRequest, MessageResponse
from app.application.message_service import MessageService
from app.domain.models import Analysis


class _FakeClassifier:
    def __init__(self, analysis: Analysis):
        self._analysis = analysis

    async def classify(self, text, history=None):
        return self._analysis


class _FakeGeocoder:
    async def geocode(self, query):
        return None  # 지역 없음 → 현재 위치 유지


class _AnywhereGeocoder:
    """뭘 물어도 좌표를 주는 지오코더 — 잘못된 후보가 넘어오면 중심이 튄다."""

    async def geocode(self, query):
        return (35.0, 129.0)


class _CaptureHandler:
    """핸들러로 들어온 req를 캡처해 슬롯 매핑을 검증한다."""

    def __init__(self):
        self.seen: MessageRequest | None = None

    async def handle(self, req: MessageRequest) -> MessageResponse:
        self.seen = req
        return MessageResponse(intent="recommend", reply="분석.", todos=[])


def _service(analysis: Analysis, handler=None):
    handler = handler or _CaptureHandler()
    svc = MessageService(
        classifier=_FakeClassifier(analysis),
        geocoder=_FakeGeocoder(),
        recommend_handler=handler,
        info_handler=handler,
        chat_handler=handler,
    )
    return svc, handler


def _req(**kwargs):
    base = dict(text="아무거나", lat=37.5, lng=127.0)
    base.update(kwargs)
    return MessageRequest(**base)


def test_prefer_near_maps_to_distance_sort():
    svc, handler = _service(Analysis(intent="recommend", keywords=["맛집"], prefer="near"))
    asyncio.run(svc.handle(_req(text="가까운 밥집", mood="배고픔")))
    assert handler.seen.search_sort == "distance"
    assert handler.seen.search_keywords == ["맛집"]


def test_default_sort_is_accuracy():
    svc, handler = _service(Analysis(intent="recommend", keywords=["맛집"]))
    asyncio.run(svc.handle(_req(text="유명한 밥집", mood="배고픔")))
    assert handler.seen.search_sort == "accuracy"


def test_geo_keyword_filtered():
    # 분류기가 지역명을 keywords에 섞어도 검색어에서 제외된다
    svc, handler = _service(Analysis(intent="recommend", keywords=["강남역", "방탈출"]))
    asyncio.run(svc.handle(_req(text="강남역 방탈출", mood="심심")))
    assert handler.seen.search_keywords == ["방탈출"]


def test_vague_without_context_asks_back():
    # 막연 + 기분/대화 없음 → 핸들러 안 가고 1회 되묻기 + 선택지 칩
    svc, handler = _service(Analysis(intent="recommend", vague=True))
    resp = asyncio.run(svc.handle(_req(text="그냥 추천해줘")))
    assert handler.seen is None  # 핸들러 미호출
    assert resp.todos == []
    assert "어떤" in resp.reply  # 되묻는 문장
    assert len(resp.options) >= 5  # fe 버튼용 선택지


def test_vague_with_weather_recommends_directly():
    # 막연 요청이라도 날씨 신호가 있으면 되묻지 말고 바로 추천 (포위망 축소)
    svc, handler = _service(Analysis(intent="recommend", vague=True))
    resp = asyncio.run(svc.handle(_req(text="오늘 뭐하지", weather="비, 18도")))
    assert handler.seen is not None  # 되묻지 않고 추천 핸들러 호출
    assert resp.options == []


def test_broad_activity_chips_respect_weather():
    # 카테고리축 좁히기 칩은 비 오면 야외 계열 제외
    svc, _ = _service(Analysis(intent="recommend", vague=False))
    resp = asyncio.run(svc.handle(_req(text="놀러 갈까", weather="비, 18도")))
    assert resp.options and "야외/산책" not in resp.options


def test_non_vague_has_no_options():
    # 구체적 요청엔 칩을 붙이지 않는다
    svc, _ = _service(Analysis(intent="recommend", keywords=["맛집"]))
    resp = asyncio.run(svc.handle(_req(text="밥집 추천", mood="배고픔")))
    assert resp.options == []


def test_place_type_word_never_moves_center():
    # "PC방 가고싶어"의 'PC방'(장소종류)이 지역으로 오인돼 중심이 튀면 안 됨
    handler = _CaptureHandler()
    svc = MessageService(
        classifier=_FakeClassifier(Analysis(intent="recommend", keywords=["PC방"])),
        geocoder=_AnywhereGeocoder(),
        recommend_handler=handler,
        info_handler=handler,
        chat_handler=handler,
    )
    asyncio.run(svc.handle(_req(text="PC방 가고싶어", mood="심심")))
    assert (handler.seen.lat, handler.seen.lng) == (37.5, 127.0)  # 현재 위치 유지


def test_food_word_never_moves_center():
    # '밥집'은 분류기 keywords가 "맛집"으로 정규화돼도 장소종류 사전으로 걸러진다
    handler = _CaptureHandler()
    svc = MessageService(
        classifier=_FakeClassifier(Analysis(intent="recommend", keywords=["맛집"])),
        geocoder=_AnywhereGeocoder(),
        recommend_handler=handler,
        info_handler=handler,
        chat_handler=handler,
    )
    asyncio.run(svc.handle(_req(text="밥집 가고싶어", mood="배고픔")))
    assert (handler.seen.lat, handler.seen.lng) == (37.5, 127.0)


def test_narrow_cap_forces_recommend():
    # 이미 두 번 좁혔으면(assistant '?' 턴 2개) vague여도 무조건 추천 진행
    svc, handler = _service(
        Analysis(intent="recommend", vague=True, question="더요?", options=["a", "b"])
    )
    history = [
        {"role": "assistant", "content": "뭐가 당기세요?"},
        {"role": "user", "content": "먹으러 가기"},
        {"role": "assistant", "content": "어떤 음식이 좋으세요?"},
        {"role": "user", "content": "한식"},
    ]
    resp = asyncio.run(svc.handle(_req(text="한식", history=history)))
    assert handler.seen is not None  # 되묻지 않고 핸들러 호출
    assert resp.intent == "recommend"


def test_bad_llm_options_fall_back_to_rule_chips():
    # LLM 옵션이 부실(1개)하면 규칙 칩으로 폴백
    svc, _ = _service(Analysis(intent="recommend", vague=True, question="뭐요?", options=["하나"]))
    resp = asyncio.run(svc.handle(_req(text="추천")))
    assert len(resp.options) >= 5  # option_builder 칩


def test_empty_question_falls_back():
    svc, _ = _service(Analysis(intent="recommend", vague=True, options=["먹기", "놀기"]))
    resp = asyncio.run(svc.handle(_req(text="추천")))
    assert resp.reply.endswith("?")  # 기본 질문으로 대체


def test_broad_activity_narrows_first():
    # "놀러/데이트"처럼 '뭘' 넓은 활동 + 구체 종류 없음 → 카테고리 좁히기 질문
    svc, handler = _service(Analysis(intent="recommend", vague=False))
    resp = asyncio.run(svc.handle(_req(text="놀러 어디 갈까", weather="맑음")))
    assert handler.seen is None  # 추천 핸들러 미호출(좁히기)
    assert len(resp.options) >= 5


def test_picnic_goes_direct_not_narrow():
    # 소풍/나들이는 '어디로(위치)' 축 → 카테고리 안 묻고 공원 직접 추천
    svc, handler = _service(Analysis(intent="recommend", keywords=["공원"], vague=False))
    asyncio.run(svc.handle(_req(text="소풍 갈래", weather="맑음")))
    assert handler.seen is not None  # 좁히기 없이 바로 추천


def test_broad_activity_with_category_recommends_directly():
    # "데이트 카페처럼" 구체 종류가 있으면 좁히기 없이 바로 추천
    svc, handler = _service(Analysis(intent="recommend", keywords=["카페"], vague=False))
    asyncio.run(svc.handle(_req(text="데이트할 카페", mood="설렘")))
    assert handler.seen is not None  # 바로 추천
    assert handler.seen.search_keywords == ["카페"]


def test_broad_branch_answer_forces_second_question():
    # LLM이 vague=false로 건너뛰어도, 답이 '큰 갈래'면 코드가 세부 질문 강제
    svc, handler = _service(Analysis(intent="recommend", keywords=["맛집"], vague=False))
    history = [{"role": "assistant", "content": "뭐가 당기세요?"}, {"role": "user", "content": "먹으러 가기"}]
    resp = asyncio.run(svc.handle(_req(text="먹으러 가기", history=history[:1])))
    assert handler.seen is None  # 추천 대신 되묻기
    assert "음식" in resp.reply
    assert "한식" in resp.options


def test_branch_backstop_respects_cap():
    # 이미 2회 좁혔으면 큰 갈래 답이어도 강제 질문 없이 추천
    svc, handler = _service(Analysis(intent="recommend", keywords=["맛집"], vague=False))
    history = [
        {"role": "assistant", "content": "뭐가 당기세요?"},
        {"role": "user", "content": "먹으러 가기"},
        {"role": "assistant", "content": "어떤 음식이 좋으세요?"},
        {"role": "user", "content": "먹으러 가기"},
    ]
    asyncio.run(svc.handle(_req(text="먹으러 가기", history=history)))
    assert handler.seen is not None  # 추천 진행


def test_geo_keyword_does_not_block_center_move():
    # 분류기가 keywords에 '강남역'을 잘못 섞어도 위치 해석(중심 이동)은 살아야 함
    handler = _CaptureHandler()
    svc = MessageService(
        classifier=_FakeClassifier(Analysis(intent="recommend", keywords=["강남역"])),
        geocoder=_AnywhereGeocoder(),
        recommend_handler=handler,
        info_handler=handler,
        chat_handler=handler,
    )
    asyncio.run(svc.handle(_req(text="강남역 갈 건데 유명한 거 추천", mood="설렘")))
    assert (handler.seen.lat, handler.seen.lng) == (35.0, 129.0)  # 중심 이동됨
    assert handler.seen.search_keywords == []  # 지역명은 검색어에서 제외


def test_vague_with_mood_recommends_directly():
    # 기분(상황 신호)이 있으면 되묻지 말고 바로 추천 (포위망 축소)
    svc, handler = _service(
        Analysis(intent="recommend", vague=True, question="뭐가 당기세요?",
                 options=["먹으러 가기", "카페", "놀거리"])
    )
    resp = asyncio.run(svc.handle(_req(text="그냥 추천해줘", mood="심심")))
    assert handler.seen is not None  # 되묻지 않고 추천
    assert resp.intent == "recommend"
