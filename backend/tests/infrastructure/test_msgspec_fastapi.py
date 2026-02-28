import json

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from infrastructure.msgspec_fastapi import (
    AppStruct,
    MsgSpecBody,
    MsgSpecJSONRequest,
    MsgSpecJSONResponse,
    MsgSpecRoute,
    _contains_msgspec_struct,
    _merge_response_schema,
)


class SamplePayload(AppStruct):
    value: int


@pytest.mark.asyncio
async def test_msgspec_json_request_caches_decoded_body():
    body = b'{"value": 7}'

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = MsgSpecJSONRequest(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": "/",
            "raw_path": b"/",
            "scheme": "http",
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 123),
            "server": ("testserver", 80),
        },
        receive,
    )

    first = await request.json()
    second = await request.json()

    assert first == {"value": 7}
    assert second == first


@pytest.mark.asyncio
async def test_msgspec_json_request_raises_json_decode_error():
    async def receive():
        return {"type": "http.request", "body": b"{", "more_body": False}

    request = MsgSpecJSONRequest(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": "/",
            "raw_path": b"/",
            "scheme": "http",
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 123),
            "server": ("testserver", 80),
        },
        receive,
    )

    with pytest.raises(json.JSONDecodeError):
        await request.json()


def test_app_struct_iteration_and_json_response_render():
    payload = SamplePayload(value=5)

    assert dict(payload) == {"value": 5}

    response = MsgSpecJSONResponse(content=payload)
    assert response.body == b'{"value":5}'


def test_msgspec_body_and_route_work_with_fastapi():
    app = FastAPI()
    router = APIRouter(route_class=MsgSpecRoute)

    @router.post("/items", response_model=SamplePayload)
    async def create_item(body: SamplePayload = MsgSpecBody(SamplePayload)):
        return body

    app.include_router(router)
    client = TestClient(app)

    ok = client.post("/items", json={"value": 11})
    assert ok.status_code == 200
    assert ok.json() == {"value": 11}

    bad = client.post("/items", json={"value": "nope"})
    assert bad.status_code == 422


def test_contains_msgspec_struct_and_merge_response_schema():
    assert _contains_msgspec_struct(SamplePayload) is True
    assert _contains_msgspec_struct(list[SamplePayload]) is True
    assert _contains_msgspec_struct(str | None) is False

    merged = _merge_response_schema(
        {"responses": {"200": {"description": "ok"}}},
        {"type": "object", "properties": {"value": {"type": "integer"}}},
    )

    schema = merged["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["type"] == "object"
    assert "value" in schema["properties"]
