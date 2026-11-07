import httpx
import pytest

from fieldwatch.http import with_retries


def _status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example")
    return httpx.HTTPStatusError(
        f"Server error '{status}'", request=request, response=httpx.Response(status, request=request)
    )


def test_retries_on_502_then_succeeds():
    calls = []

    def fetch():
        calls.append(1)
        if len(calls) < 3:
            raise _status_error(502)
        return {"ok": True}

    out = with_retries(fetch, attempts=3, delays=(0.0, 0.0))
    assert out == {"ok": True}
    assert len(calls) == 3


def test_no_retry_on_client_error():
    calls = []

    def fetch():
        calls.append(1)
        raise _status_error(404)

    with pytest.raises(httpx.HTTPStatusError):
        with_retries(fetch, attempts=3, delays=(0.0, 0.0))
    assert len(calls) == 1


def test_retries_on_connection_error():
    calls = []

    def fetch():
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("down", request=httpx.Request("GET", "https://example"))
        return {"ok": True}

    out = with_retries(fetch, attempts=3, delays=(0.0, 0.0))
    assert out == {"ok": True}
    assert len(calls) == 2


def test_gives_up_after_last_attempt():
    calls = []

    def fetch():
        calls.append(1)
        raise _status_error(503)

    with pytest.raises(httpx.HTTPStatusError):
        with_retries(fetch, attempts=3, delays=(0.0, 0.0))
    assert len(calls) == 3
