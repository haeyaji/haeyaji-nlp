from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

Category = Literal["야외", "실내", "휴식", "생산성", "사람만나기", "맛집/카페"]

# 사용자 메시지 의도 (라우팅 키). "action"은 규칙 파서가 방출(LLM은 안 씀).
Intent = Literal["recommend", "info", "chat", "action"]

# be가 실행할 액션 종류 (nlp는 파싱만, 실행은 be)
ActionType = Literal["schedule.create", "schedule.share", "schedule.fill"]


class CamelModel(BaseModel):
    """API 경계 모델: 출력은 camelCase, 입력은 camel/snake 둘 다 허용.

    내부 파이썬 코드는 계속 snake_case로 접근한다(populate_by_name).
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Turn(CamelModel):
    """대화 히스토리 한 턴. be가 세션에서 최근 N턴을 구성해 전달한다."""

    role: Literal["user", "assistant"]
    content: str


class Analysis(BaseModel):
    """분류기(LLM) 출력 — 요청을 슬롯으로 분해해 '점점 좁히기(포위망)'의 입력이 된다.

    keywords: [무엇] 찾는 '장소 종류/활동' 카카오 검색어 (PC방·볼링장·맛집 등).
      하드코딩 리스트로 못 잡는 임의 카테고리를 LLM이 직접 추출한다. 없으면 [].
    prefer:   [필터] 랭킹 선호. "유명한/핫한"→famous(정확도순), "가까운/근처"→near(거리순).
    vague:    [좁힘] 좋은 추천을 하기에 카테고리 정보가 부족하면 True.
      True면 question/options로 한 단계 좁혀 되묻는다 (코드가 최대 2회로 캡).
    question: [좁힘] 되물을 질문 — LLM이 대화 맥락에 맞게 생성.
    options:  [좁힘] 버튼 선택지 — LLM이 현재 좁힘 단계에 맞게 생성.
      (예: 1단계 "먹으러 가기/카페/놀거리…" → 2단계 "한식/일식/중식…")
    (위치 슬롯은 location_extractor+geocoder가 별도로 해석한다)
    """

    intent: Intent
    keywords: list[str] = Field(default_factory=list)
    prefer: Literal["famous", "near"] | None = None
    vague: bool = False
    question: str = ""
    options: list[str] = Field(default_factory=list)


class Place(BaseModel):
    """카카오에서 가져온 실제 장소 (RAG 데이터)."""

    name: str
    category: str
    address: str
    url: str = ""
    distance_m: int | None = None
    x: float | None = None  # 경도
    y: float | None = None  # 위도


class TodoItem(CamelModel):
    title: str = Field(description="할 일 한 줄")
    reason: str = Field(description="왜 지금 이걸 추천하는지 (상황 근거)")
    category: Category
    estimated_minutes: int = Field(description="예상 소요 시간(분)")
    place_name: str | None = Field(
        default=None, description="연결된 실제 장소 이름 (장소 기반 추천일 때만)"
    )
    # 아래는 LLM이 아니라 코드가 실제 카카오 Place에서 채운다 (지도 마커/거리용)
    place_url: str | None = Field(default=None, description="카카오맵 링크")
    x: float | None = Field(default=None, description="경도 (지도 마커)")
    y: float | None = Field(default=None, description="위도 (지도 마커)")
    distance_m: int | None = Field(default=None, description="현재 위치에서 거리(m)")


class TodoRecommendation(BaseModel):
    analysis: str = Field(description="현재 상황 한 문장 분석")
    todos: list[TodoItem] = Field(description="추천 할 일 3~5개")


class PlannedTodo(BaseModel):
    """LLM이 생성하는 '계획' 단위. 실제 장소는 코드가 search_query로 검색해 채운다.

    LLM은 활동/카테고리와 '검색어'만 정한다(가게 이름을 지어내지 않음 = 환각 차단).
    """

    title: str = Field(description="구체적 할 일 한 줄")
    reason: str = Field(description="왜 지금 이걸 추천하는지")
    category: Category
    estimated_minutes: int = Field(description="예상 소요 시간(분)")
    search_query: str | None = Field(
        default=None,
        description="이 활동에 맞는 카카오 검색어(북카페/라멘/전시회 등). 장소 불필요 시 null",
    )


class RecommendationPlan(BaseModel):
    """LLM 출력: 상황 분석 + 활동 계획 목록. 장소는 아직 안 붙음."""

    analysis: str = Field(description="현재 상황 한 문장 분석")
    todos: list[PlannedTodo] = Field(description="추천 활동 3~5개")


class TimeRange(CamelModel):
    """일정 시간 범위 (규칙 파서가 텍스트에서 추출).

    nlp은 실제 날짜가 없으므로 '몇 시'까지만 뽑는다. 오전/오후 힌트(meridiem)와
    요일을 합쳐 절대 datetime으로 확정하는 것은 be의 몫.
    """

    start_hour: int = Field(description="시작 시(0~23, 12시간제면 meridiem과 함께)")
    start_minute: int = 0
    end_hour: int | None = Field(default=None, description="종료 시 (단일 시각이면 null)")
    end_minute: int = 0
    meridiem: Literal["am", "pm"] | None = Field(
        default=None, description="오전/오후 힌트. 절대시각 확정은 be"
    )
    raw: str = Field(default="", description="원문에서 인식한 시간 표현")


class Action(CamelModel):
    """be가 실행할 구조화 액션. nlp은 파싱만 하고 실행/저장은 be가 한다."""

    type: ActionType
    time_range: TimeRange | None = None
    title: str | None = Field(default=None, description="일정 제목/활동")
    place_name: str | None = Field(default=None, description="확정된 장소 이름(있으면)")
    place_url: str | None = None
    target_friend: str | None = Field(
        default=None, description="공유 대상 raw 멘션. 이름 해석은 be. '친구'면 null(be가 피커)"
    )
    ref: str | None = Field(
        default=None, description='직전 액션 참조. 공유가 방금 만든 일정을 가리킬 때 "$lastCreated"'
    )
    requires_confirmation: bool = Field(
        default=True, description="be가 실행 전 사용자 확인을 받을지"
    )


class UserProfile(CamelModel):
    """사용자 선호 프로필. be가 설문/선택이력으로 채워 전달한다.

    전부 선택값 — 없으면(신규 유저) 일반 추천으로 동작.
    """

    preferred_categories: list[str] = Field(
        default_factory=list, description="선호 카테고리 (설문/이력)"
    )
    vibe: str | None = Field(default=None, description='선호 분위기 (예: "조용", "활기")')
    intensity: str | None = Field(
        default=None, description='활동 강도 선호 (예: "가볍게", "적극적")'
    )
    avoid: list[str] = Field(default_factory=list, description="회피 요소")
    recent_selections: list[str] = Field(
        default_factory=list, description="최근 선택(행동 신호)"
    )
