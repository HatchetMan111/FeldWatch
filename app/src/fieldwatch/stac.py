from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .http import post_json

STAC_URL = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-l2a"
ASSETS = ("red", "nir", "scl")


@dataclass(frozen=True)
class SceneRef:
    id: str
    datetime: str
    cloud_cover: float
    hrefs: dict[str, str]


def _window(months: int, now: datetime | None) -> str:
    end = now or datetime.now(timezone.utc)
    start = end - timedelta(days=int(months * 30.44))
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return f"{start.strftime(fmt)}/.."


def search(
    geometry: dict,
    months: int = 12,
    max_cloud: int = 80,
    *,
    limit: int = 500,
    max_scenes: int = 36,
    now: datetime | None = None,
    fetch=post_json,
) -> list[SceneRef]:
    payload = fetch(
        STAC_URL,
        {
            "collections": [COLLECTION],
            "intersects": geometry,
            "datetime": _window(months, now),
            "query": {"eo:cloud_cover": {"lt": max_cloud}},
            "limit": limit,
            "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        },
    )
    features = payload.get("features")
    if features is None:
        raise ValueError("STAC-Antwort ohne 'features'")

    scenes: list[SceneRef] = []
    for feature in features:
        assets = feature.get("assets") or {}
        hrefs = {
            key: assets[key]["href"]
            for key in ASSETS
            if key in assets and "href" in assets[key]
        }
        if len(hrefs) != len(ASSETS):
            continue
        props = feature.get("properties") or {}
        scenes.append(
            SceneRef(
                id=feature.get("id", ""),
                datetime=props.get("datetime", ""),
                cloud_cover=float(props.get("eo:cloud_cover", 100.0)),
                hrefs=hrefs,
            )
        )
    scenes.sort(key=lambda s: s.datetime, reverse=True)
    scenes = _best_per_day(scenes)
    return _thin(scenes, max_scenes)


def _best_per_day(scenes: list[SceneRef]) -> list[SceneRef]:
    best: dict[str, SceneRef] = {}
    for scene in scenes:
        day = scene.datetime[:10]
        current = best.get(day)
        if current is None or scene.cloud_cover < current.cloud_cover:
            best[day] = scene
    return sorted(best.values(), key=lambda s: s.datetime, reverse=True)


def _thin(scenes: list[SceneRef], max_scenes: int) -> list[SceneRef]:
    if max_scenes <= 0 or len(scenes) <= max_scenes:
        return scenes
    if max_scenes == 1:
        return scenes[:1]
    step = (len(scenes) - 1) / (max_scenes - 1)
    keep = sorted({int(round(i * step)) for i in range(max_scenes)})
    return [scenes[i] for i in keep]
