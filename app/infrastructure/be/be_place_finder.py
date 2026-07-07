import httpx

from app.domain.models import Place

_SEARCH_PATH = "/api/places/search"


class BePlaceFinder:
    """PlaceFinder 포트의 be 프록시 구현 (async).

    카카오 직접 호출 대신 be의 장소검색 엔드포인트를 부른다.
    카카오 REST 키는 be가 보유 — nlp는 검색어·좌표·정렬만 전달한다.
    실패/미발견 시 빈 리스트 → 호출측이 graceful 폴백.
    """

    def __init__(self, base_url: str, timeout: float = 5.0, client: httpx.AsyncClient | None = None):
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def search(
        self,
        query: str,
        lat: float,
        lng: float,
        radius_m: int,
        size: int = 5,
        sort: str = "accuracy",
        category_group_code: str | None = None,
    ) -> list[Place]:
        params: dict = {
            "query": query,
            "lat": lat,
            "lng": lng,
            "radiusM": radius_m,
            "size": size,
            "sort": sort,
        }
        if category_group_code:
            params["categoryGroupCode"] = category_group_code
        try:
            resp = await self._client.get(f"{self._base_url}{_SEARCH_PATH}", params=params)
            resp.raise_for_status()
            docs = resp.json().get("places", [])
        except (httpx.HTTPError, ValueError):
            return []

        places: list[Place] = []
        for d in docs:
            dist = d.get("distanceM")
            places.append(
                Place(
                    name=d.get("name", ""),
                    category=d.get("category", ""),
                    address=d.get("address", ""),
                    url=d.get("url", ""),
                    distance_m=int(dist) if dist is not None else None,
                    x=float(d["x"]) if d.get("x") is not None else None,
                    y=float(d["y"]) if d.get("y") is not None else None,
                )
            )
        return places
