"""Every error response uses the contract shape {"error": {code, message, details}}."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import ApiException
from app.contracts_gen.common_schema import ErrorResponse
from app.main import create_app


def app_with_test_routes() -> FastAPI:
    app = create_app()

    @app.get("/api/v1/_test/items/{item_id}")
    def item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    @app.post("/api/v1/_test/plans/{plan_id}/approve")
    def approve(plan_id: int) -> dict[str, int]:
        raise ApiException(409, "plan_not_editable", "Plan is already approved", {"plan_id": plan_id})

    @app.get("/api/v1/_test/crash")
    def crash() -> None:
        raise RuntimeError("secret database password in this message")

    return app


client = TestClient(app_with_test_routes(), raise_server_exceptions=False)


def error_of(response: object) -> ErrorResponse:
    return ErrorResponse.model_validate(response.json())  # type: ignore[attr-defined]


def test_unknown_route_is_not_found() -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert error_of(response).error.code == "not_found"


def test_validation_error_lists_the_bad_fields() -> None:
    response = client.get("/api/v1/_test/items/not-a-number")

    assert response.status_code == 422
    error = error_of(response).error
    assert error.code == "validation_error"
    assert error.details is not None
    assert error.details["fields"][0]["loc"] == ["path", "item_id"]


def test_api_exception_keeps_code_message_and_details() -> None:
    response = client.post("/api/v1/_test/plans/7/approve")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "plan_not_editable",
            "message": "Plan is already approved",
            "details": {"plan_id": 7},
        }
    }


def test_unexpected_errors_are_internal_and_leak_nothing() -> None:
    response = client.get("/api/v1/_test/crash")

    assert response.status_code == 500
    assert response.json() == {"error": {"code": "internal", "message": "Internal error"}}
    assert "password" not in response.text


def test_wrong_method_still_uses_the_contract_shape() -> None:
    response = client.post("/api/v1/health")

    assert response.status_code == 405
    assert error_of(response).error.code == "validation_error"


def test_openapi_documents_error_response_not_fastapi_default() -> None:
    spec = create_app().openapi()
    schemas = spec["components"]["schemas"]
    health = spec["paths"]["/api/v1/health"]["get"]["responses"]

    assert "ErrorResponse" in schemas
    assert "HTTPValidationError" not in schemas
    assert health["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/HealthResponse"
    }
    assert health["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
