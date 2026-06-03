"""Tests for LambdaFunctionExpectation.to_respond_with."""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from mypy_boto3_lambda.client import LambdaClient

from aws_expect import expect_lambda
from aws_expect.exceptions import LambdaResponseMismatchError


class TestToRespondWithStatusOnly:
    """LAMBDA-01: status_code without expected_payload."""

    def test_passes_when_status_matches(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        # lambda_function returns {"statusCode": 200, "body": "hello"}
        result = expect_lambda(lambda_client).to_respond_with(
            lambda_function, status_code=200
        )
        assert result["statusCode"] == 200

    def test_raises_when_status_mismatches(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        with pytest.raises(LambdaResponseMismatchError) as exc_info:
            expect_lambda(lambda_client).to_respond_with(
                lambda_function, status_code=404
            )
        assert exc_info.value.function_name == lambda_function
        assert exc_info.value.reason == "payload_mismatch"
        assert exc_info.value.expected_status == 404
        assert exc_info.value.expected_payload is None
        assert exc_info.value.actual == {"statusCode": 200, "body": "hello"}


class TestToRespondWithPayloadOnly:
    """LAMBDA-01: expected_payload without status_code."""

    def test_passes_when_body_subset_matches(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        # lambda_function_json_body returns body={"message": "hello", "status": "ok"}
        result = expect_lambda(lambda_client).to_respond_with(
            lambda_function_json_body, expected_payload={"message": "hello"}
        )
        assert result["statusCode"] == 200

    def test_raises_when_body_mismatches(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        with pytest.raises(LambdaResponseMismatchError) as exc_info:
            expect_lambda(lambda_client).to_respond_with(
                lambda_function_json_body, expected_payload={"message": "wrong"}
            )
        assert exc_info.value.reason == "payload_mismatch"
        assert exc_info.value.expected_payload == {"message": "wrong"}
        assert exc_info.value.expected_status is None
        assert exc_info.value.actual is not None


class TestToRespondWithBothArgs:
    """LAMBDA-01: both status_code and expected_payload."""

    def test_passes_when_both_match(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        result = expect_lambda(lambda_client).to_respond_with(
            lambda_function_json_body,
            status_code=200,
            expected_payload={"message": "hello"},
        )
        assert result["statusCode"] == 200

    def test_raises_when_status_mismatches(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        with pytest.raises(LambdaResponseMismatchError) as exc_info:
            expect_lambda(lambda_client).to_respond_with(
                lambda_function_json_body,
                status_code=500,
                expected_payload={"message": "hello"},
            )
        assert exc_info.value.reason == "payload_mismatch"
        assert exc_info.value.expected_status == 500
        assert exc_info.value.expected_payload == {"message": "hello"}


class TestToRespondWithValueErrorGuard:
    """D-05: calling with neither status_code nor expected_payload raises ValueError."""

    def test_raises_value_error_when_no_args(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        with pytest.raises(
            ValueError,
            match="At least one of status_code or expected_payload must be provided.",
        ):
            expect_lambda(lambda_client).to_respond_with(lambda_function)


class TestToRespondWithFunctionError:
    """D-04: FunctionError branch passes actual=None to LambdaResponseMismatchError."""

    def test_raises_with_none_actual_on_function_error(
        self, lambda_client: LambdaClient, error_lambda_function: str
    ) -> None:
        with pytest.raises(LambdaResponseMismatchError) as exc_info:
            expect_lambda(lambda_client).to_respond_with(
                error_lambda_function, status_code=200
            )
        assert exc_info.value.reason == "function_error"
        assert exc_info.value.actual is None
        assert exc_info.value.expected_status == 200


class TestToRespondWithDeepBody:
    """LAMBDA-02: deep nested body matching via _deep_matches."""

    def test_partial_nested_dict_matches(
        self, lambda_client: LambdaClient, lambda_function_nested_body: str
    ) -> None:
        # actual body: {"data": {"id": 42, "tags": ["a", "b"]}, "meta": {"version": 1}}
        # partial match: only check data.id
        result = expect_lambda(lambda_client).to_respond_with(
            lambda_function_nested_body, expected_payload={"data": {"id": 42}}
        )
        assert result["statusCode"] == 200

    def test_raises_when_nested_value_mismatches(
        self, lambda_client: LambdaClient, lambda_function_nested_body: str
    ) -> None:
        with pytest.raises(LambdaResponseMismatchError) as exc_info:
            expect_lambda(lambda_client).to_respond_with(
                lambda_function_nested_body, expected_payload={"data": {"id": 99}}
            )
        assert exc_info.value.reason == "payload_mismatch"

    def test_full_nested_dict_matches(
        self, lambda_client: LambdaClient, lambda_function_nested_body: str
    ) -> None:
        result = expect_lambda(lambda_client).to_respond_with(
            lambda_function_nested_body,
            expected_payload={
                "data": {"id": 42, "tags": ["a", "b"]},
                "meta": {"version": 1},
            },
        )
        assert result["statusCode"] == 200


class TestToRespondWithStatusCode:
    """StatusCode on the invoke response is not 200 or 202."""

    def test_raises_invalid_status_code_when_301(
        self, lambda_client: LambdaClient
    ) -> None:
        fake = {
            "StatusCode": 301,
            "Payload": io.BytesIO(b""),
        }
        with patch.object(lambda_client, "invoke", return_value=fake):
            with pytest.raises(LambdaResponseMismatchError) as exc_info:
                expect_lambda(lambda_client).to_respond_with("any-fn", status_code=200)
        assert exc_info.value.reason == "invalid_status_code"
        assert exc_info.value.actual is None

    def test_raises_invalid_status_code_when_500(
        self, lambda_client: LambdaClient
    ) -> None:
        fake = {
            "StatusCode": 500,
            "Payload": io.BytesIO(b'{"statusCode": 500, "body": "err"}'),
        }
        with patch.object(lambda_client, "invoke", return_value=fake):
            with pytest.raises(LambdaResponseMismatchError) as exc_info:
                expect_lambda(lambda_client).to_respond_with("any-fn", status_code=200)
        assert exc_info.value.reason == "invalid_status_code"
        assert exc_info.value.actual is None


class TestToRespondWithPayloadEdgeCases:
    """Empty payload, invalid JSON, and non-dict payload types."""

    def test_raises_empty_payload_reason(self, lambda_client: LambdaClient) -> None:
        fake = {
            "StatusCode": 200,
            "Payload": io.BytesIO(b""),
        }
        with patch.object(lambda_client, "invoke", return_value=fake):
            with pytest.raises(LambdaResponseMismatchError) as exc_info:
                expect_lambda(lambda_client).to_respond_with("any-fn", status_code=200)
        assert exc_info.value.reason == "empty_payload"
        assert exc_info.value.actual is None

    def test_raises_invalid_json_reason(self, lambda_client: LambdaClient) -> None:
        fake = {
            "StatusCode": 200,
            "Payload": io.BytesIO(b"this is not json"),
        }
        with patch.object(lambda_client, "invoke", return_value=fake):
            with pytest.raises(LambdaResponseMismatchError) as exc_info:
                expect_lambda(lambda_client).to_respond_with("any-fn", status_code=200)
        assert exc_info.value.reason == "invalid_json"
        assert exc_info.value.actual is None

    def test_raises_invalid_payload_type_reason(
        self,
        lambda_client: LambdaClient,
        lambda_function_empty_payload: str,
    ) -> None:
        with pytest.raises(LambdaResponseMismatchError) as exc_info:
            expect_lambda(lambda_client).to_respond_with(
                lambda_function_empty_payload, status_code=200
            )
        assert exc_info.value.reason == "invalid_payload_type"
        assert exc_info.value.actual is None
