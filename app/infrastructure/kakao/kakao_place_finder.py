import httpx

from app.domain.models import Place

_KAKAO_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class KakaoPlaceFinder:
    """PlaceFinder 포트의 카카오 로컬 API 구현 (async)."""

    def __init__(self, rest_key: str, timeout: float = 5.0):
        self._rest_key = rest_key
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"KakaoAK {rest_key}"}, timeout=timeout
        )

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
        # x=경도, y=위도, radius(m)를 넣으면 distance가 채워진다.
        # sort=accuracy: 카카오 랭킹(유명·검증된 곳 우선) / distance: 최단거리순.
        # category_group_code: FD6(음식점)/CE7(카페) 등 — 다른 종류 섞임 방지 하드 필터.
        params = {
            "query": query,
            "x": lng,
            "y": lat,
            "radius": radius_m,
            "size": size,
            "sort": sort,
        }
        if category_group_code:
            params["category_group_code"] = category_group_code
        resp = await self._client.get(_KAKAO_URL, params=params)
        resp.raise_for_status()
        docs = resp.json().get("documents", [])

        places: list[Place] = []
        for d in docs:
            dist = d.get("distance")
            places.append(
                Place(
                    name=d["place_name"],
                    category=d.get("category_group_name") or d.get("category_name", ""),
                    address=d.get("road_address_name") or d.get("address_name", ""),
                    url=d.get("place_url", ""),
                    distance_m=int(dist) if dist else None,
                    x=float(d["x"]) if d.get("x") else None,
                    y=float(d["y"]) if d.get("y") else None,
                )
            )
        return places
