import httpx

_GEOCODE_PATH = "/api/places/geocode"


class BeGeocoder:
    """Geocoder 포트의 be 프록시 구현 (async).

    지역/장소명 → 좌표 변환을 be에 위임. 카카오 키는 be가 보유.
    200이면 (위도, 경도), 204(미발견)/실패 시 None → 호출측이 현재 위치로 폴백.
    """

    def __init__(self, base_url: str, timeout: float = 5.0, client: httpx.AsyncClient | None = None):
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def geocode(self, query: str) -> tuple[float, float] | None:
        try:
            resp = await self._client.get(
                f"{self._base_url}{_GEOCODE_PATH}", params={"query": query}
            )
            if resp.status_code == 204:
                return None
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not data:
            return None
        try:
            return (float(data["lat"]), float(data["lng"]))
        except (KeyError, TypeError, ValueError):
            return None
