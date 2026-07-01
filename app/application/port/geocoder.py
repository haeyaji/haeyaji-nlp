from typing import Protocol


class Geocoder(Protocol):
    """지역/장소명 → 좌표 변환 포트. 구현은 infrastructure(KakaoGeocoder)."""

    async def geocode(self, query: str) -> tuple[float, float] | None:
        """성공 시 (위도, 경도), 실패/미발견 시 None."""
        ...
