from pydantic import Field

from app.domain.models import CamelModel, Intent, TodoItem, Turn, UserProfile


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
    # 내부용: 분류기가 추출한 검색어를 service가 채워 핸들러로 전달 (클라이언트는 안 보냄)
    search_keywords: list[str] = Field(
        default_factory=list, description="내부용(service가 채움): 검색할 장소 종류"
    )


class MessageResponse(CamelModel):
    """모든 인텐트 공통 응답. reply는 항상, todos는 추천일 때만 채워진다."""

    intent: Intent
    reply: str = Field(description="사용자에게 보여줄 자연어 응답")
    todos: list[TodoItem] = Field(default_factory=list, description="추천 할 일 (추천 인텐트만)")
