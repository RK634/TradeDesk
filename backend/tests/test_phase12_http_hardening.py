from __future__ import annotations

import re


def test_api_responses_include_security_headers_and_request_id(client) -> None:
    response = client.get("/api/v1/health/live", headers={"X-Request-ID": "release-check-123"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "release-check-123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["Cache-Control"] == "no-store"


def test_invalid_request_id_is_replaced_with_server_generated_uuid(client) -> None:
    response = client.get("/api/v1/health/live", headers={"X-Request-ID": "bad request id with spaces"})
    assert response.status_code == 200
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        response.headers["X-Request-ID"],
    )


def test_disallowed_browser_origin_does_not_receive_cors_permission(client) -> None:
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-token",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_json_logs_include_the_active_request_id() -> None:
    import json
    import logging

    from app.core.logging import JsonFormatter
    from app.core.request_context import request_id_context

    token = request_id_context.set("correlated-request-42")
    try:
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "test event", (), None)
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_context.reset(token)
    assert payload["request_id"] == "correlated-request-42"
