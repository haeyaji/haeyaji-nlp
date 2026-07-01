from typing import Protocol

from app.domain.models import Place


class PlaceFinder(Protocol):
    """장소 검색 포트 (async). 구현은 infrastructure(KakaoPlaceFinder 등)."""

    async def search(
        self,
        query: str,
        lat: float,
        lng: float,
        radius_m: int,
        size: int = 5,
        sort: str = "accuracy",
    ) -> list[Place]: ...
