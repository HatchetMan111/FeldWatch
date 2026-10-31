from __future__ import annotations

from dataclasses import dataclass

from .http import get_json

PHOTON_URL = "https://photon.komoot.io/api/"


@dataclass(frozen=True)
class Place:
    label: str
    lon: float
    lat: float


def search(query: str, *, limit: int = 1, fetch=get_json) -> Place | None:
    q = query.strip()
    if not q:
        return None
    payload = fetch(PHOTON_URL, {"q": q, "limit": limit, "lang": "de"})
    features = payload.get("features") or []
    if not features:
        return None
    feature = features[0]
    lon, lat = feature["geometry"]["coordinates"][:2]
    props = feature.get("properties") or {}
    parts = [props.get("name"), props.get("street"), props.get("city"), props.get("postcode")]
    label = ", ".join(str(p) for p in parts if p) or q
    return Place(label=label, lon=float(lon), lat=float(lat))
