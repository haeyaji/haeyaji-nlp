from pydantic import Field

from app.domain.models import (
    Action,
    CamelModel,
    Category,
    CategoryOption,
    Intent,
    ScheduleContext,
    TodoItem,
    Turn,
    UserProfile,
)


class MessageRequest(CamelModel):
    """사용자 메시지 + 맥락. 위치는 항상 들어오고(geolocation), 나머지는 선택."""

    text: str = Field(..., description="사용자가 입력한 자유 텍스트", examples=["비 오는데 뭐하지"])
    lat: float = Field(..., description="위도", examples=[37.4979])
    lng: float = Field(..., description="경도", examples=[127.0276])
    weather: str = Field("", description="날씨(있으면)", examples=["비, 18도"])
    mood: str = Field("", description="기분(있으면)", examples=["무기력"])
    time_of_day: str = Field("", description="시간대", examples=["오후 2시"])
    weekday: str = Field("", description="요일", examples=["토요일"])
    radius_m: int | None = Field(None, description="검색 반경(m). 미지정 시 기본값")
    user_profile: UserProfile | None = Field(
        None, description="사용자 선호 프로필 (be가 채워 전달). 없으면 일반 추천."
    )
    history: list[Turn] = Field(
        default_factory=list, description="최근 대화 턴 (be가 세션에서 구성). 없으면 단발 처리."
    )
    schedule_context: ScheduleContext | None = Field(
        None,
        description=(
            "일정 상황 (be가 계산해 전달). 다음 일정까지 빈 시간·그날 일정 등. "
            "없으면 일반 추천. gapMinutes가 있으면 그 안에 끝낼 활동만 추천."
        ),
    )
    selected_category: Category | None = Field(
        None,
        description=(
            "추천 2단계: 유저가 1단계에서 고른 카테고리 code (be가 실어 재호출). "
            "있으면 그 카테고리 안에서만 장소 추천. 없으면 1단계(카테고리 후보) 진행."
        ),
    )
    # 내부용: 분류기가 추출한 검색어를 service가 채워 핸들러로 전달 (클라이언트는 안 보냄)
    search_keywords: list[str] = Field(
        default_factory=list, description="내부용(service가 채움): 검색할 장소 종류"
    )
    search_sort: str = Field(
        "accuracy",
        description='내부용(service가 채움): 정렬. "가까운" 요청이면 distance, 기본 accuracy',
    )


class MessageResponse(CamelModel):
    """모든 인텐트 공통 응답. reply는 항상, todos는 추천일 때만 채워진다."""

    intent: Intent
    reply: str = Field(description="사용자에게 보여줄 자연어 응답")
    todos: list[TodoItem] = Field(default_factory=list, description="추천 할 일 (추천 인텐트만)")
    categories: list[CategoryOption] = Field(
        default_factory=list,
        description=(
            "추천 1단계 카테고리 후보 (intent=recommend_category일 때만). "
            "fe가 칩으로 렌더 → 유저 선택 → be로 choice 전송 + nlp 2단계 호출. 없으면 []"
        ),
    )
    options: list[str] = Field(
        default_factory=list,
        description="(레거시) 자유텍스트 좁히기 칩. 카테고리 2단계 도입 후 미사용. 항상 []",
    )
    actions: list[Action] = Field(
        default_factory=list,
        description="be가 실행할 구조화 액션(일정 생성/공유 등). nlp은 파싱만. 없으면 []",
    )
