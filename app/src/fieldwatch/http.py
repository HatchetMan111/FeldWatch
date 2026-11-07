from __future__ import annotations

import time

import httpx

USER_AGENT = "FieldWatch/0.1 (self-hosted; +https://github.com/HatchetMan111/FeldWatch)"

RETRY_DELAYS = (1.5, 4.0)


def with_retries(fetch, attempts: int = 3, delays: tuple[float, ...] = RETRY_DELAYS):
    """Fuehrt fetch aus und wiederholt bei 5xx oder Netzwerkfehlern.

    Die Datenquellen (AWS STAC, Open-Meteo) liefern gelegentlich kurze
    502er — ohne Wiederholung bricht dann eine ganze Analyse ab.
    """
    for attempt in range(attempts):
        try:
            return fetch()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500 or attempt == attempts - 1:
                raise
        except httpx.TransportError:
            if attempt == attempts - 1:
                raise
        if attempt < len(delays):
            time.sleep(delays[attempt])


def get_json(url: str, params: dict | None = None, timeout: float = 20.0, retries: int = 0) -> dict:
    def fetch() -> dict:
        with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    if retries:
        return with_retries(fetch, attempts=retries + 1)
    return fetch()


def post_json(url: str, payload: dict | None = None, timeout: float = 20.0, retries: int = 0) -> dict:
    def fetch() -> dict:
        with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    if retries:
        return with_retries(fetch, attempts=retries + 1)
    return fetch()
