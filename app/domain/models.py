from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["야외", "실내", "휴식", "생산성", "사람만나기", "맛집/카페"]

# 사용자 메시지 의도 (라우팅 키)
Intent = Literal["recommend", "info", "chat"]


class Turn(BaseModel):
    """대화 히스토리 한 턴. be가 세션에서 최근 N턴을 구성해 전달한다."""

    role: Literal["user", "assistant"]
    content: str


class Place(BaseModel):
    """카카오에서 가져온 실제 장소 (RAG 데이터)."""

    name: str
    category: str
    address: str
    url: str = ""
    distance_m: int | None = None
    x: float | None = None  # 경도
    y: float | None = None  # 위도


class TodoItem(BaseModel):
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


class UserProfile(BaseModel):
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
