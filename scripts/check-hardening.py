#!/usr/bin/env python3
from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen


WEB_URL = "http://localhost:4173/"
API_URL = "http://localhost:8000/health"


def fetch_headers(url: str) -> dict[str, str]:
    request = Request(url, method="GET")
    with urlopen(request, timeout=10) as response:
        headers = {key.lower(): value for key, value in response.headers.items()}
        # Drain the body to keep urllib happy on some runtimes.
        response.read()
        return headers


def main() -> int:
    try:
        web_headers = fetch_headers(WEB_URL)
        api_headers = fetch_headers(API_URL)
    except URLError as exc:
        raise SystemExit(f"failed to reach local stack: {exc}") from exc

    assert web_headers.get("x-content-type-options") == "nosniff"
    assert web_headers.get("x-frame-options") == "DENY"
    assert web_headers.get("referrer-policy") == "same-origin"
    assert web_headers.get("permissions-policy") == "geolocation=(), camera=(), microphone=()"
    assert web_headers.get("cross-origin-opener-policy") == "same-origin"
    assert web_headers.get("cross-origin-resource-policy") == "same-origin"
    assert web_headers.get("cache-control") == "no-store"
    assert web_headers.get("x-request-id")
    assert web_headers.get("server-timing", "").startswith("app;dur=")

    assert api_headers.get("x-content-type-options") == "nosniff"
    assert api_headers.get("x-frame-options") == "DENY"
    assert api_headers.get("referrer-policy") == "same-origin"
    assert api_headers.get("permissions-policy") == "geolocation=(), camera=(), microphone=()"
    assert api_headers.get("cross-origin-opener-policy") == "same-origin"
    assert api_headers.get("cross-origin-resource-policy") == "same-origin"
    assert api_headers.get("cache-control") == "no-store"
    assert api_headers.get("x-request-id")
    assert api_headers.get("server-timing", "").startswith("app;dur=")

    print(
        json.dumps(
            {
                "web": {
                    "cache_control": web_headers.get("cache-control"),
                    "security_headers": {
                        "x_content_type_options": web_headers.get("x-content-type-options"),
                        "x_frame_options": web_headers.get("x-frame-options"),
                    },
                    "request_id": web_headers.get("x-request-id"),
                    "server_timing": web_headers.get("server-timing"),
                },
                "api": {
                    "cache_control": api_headers.get("cache-control"),
                    "request_id": api_headers.get("x-request-id"),
                    "server_timing": api_headers.get("server-timing"),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
