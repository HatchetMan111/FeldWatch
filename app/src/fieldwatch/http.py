from __future__ import annotations

import httpx

USER_AGENT = "FieldWatch/0.1 (self-hosted; +https://github.com/HatchetMan111/FeldWatch)"


def get_json(url: str, params: dict | None = None, timeout: float = 20.0) -> dict:
    with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def post_json(url: str, payload: dict | None = None, timeout: float = 20.0) -> dict:
    with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
