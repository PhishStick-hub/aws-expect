"""Tests for LambdaFunctionExpectation.to_respond_with."""

from __future__ import annotations

import pytest
from mypy_boto3_lambda.client import LambdaClient

from aws_expect import expect_lambda
from aws_expect.exceptions import LambdaResponseMismatchError


class TestToRespondWithStatusOnly:
    """LAMBDA-01: status_code without body."""

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
        assert exc_info.value.expected_status == 404
        assert exc_info.value.expected_body is None
        assert exc_info.value.actual == {"statusCode": 200, "body": "hello"}


class TestToRespondWithBodyOnly:
    """LAMBDA-01: body without status_code."""

    def test_passes_when_body_subset_matches(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        # lambda_function_json_body returns body={"message": "hello", "status": "ok"}
        result = expect_lambda(lambda_client).to_respond_with(
            lambda_function_json_body, body={"message": "hello"}
        )
        assert result["statusCode"] == 200

    def test_raises_when_body_mismatches(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        with pytest.raises(LambdaResponseMismatchError) as exc_info:
            expect_lambda(lambda_client).to_respond_with(
                lambda_function_json_body, body={"message": "wrong"}
            )
        assert exc_info.value.expected_body == {"message": "wrong"}
        assert exc_info.value.expected_status is None
        assert exc_info.value.actual is not None


class TestToRespondWithBothArgs:
    """Backward-compatibility: both status_code and body still work."""

    def test_passes_when_both_match(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        result = expect_lambda(lambda_client).to_respond_with(
            lambda_function_json_body,
            status_code=200,
            body={"message": "hello"},
        )
        assert result["statusCode"] == 200

    def test_raises_when_status_mismatches(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        with pytest.raises(LambdaResponseMismatchError) as exc_info:
            expect_lambda(lambda_client).to_respond_with(
                lambda_function_json_body,
                status_code=500,
                body={"message": "hello"},
            )
        assert exc_info.value.expected_status == 500
        assert exc_info.value.expected_body == {"message": "hello"}


class TestToRespondWithValueErrorGuard:
    """D-05: calling with neither status_code nor body raises ValueError immediately."""

    def test_raises_value_error_when_no_args(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        with pytest.raises(
            ValueError, match="At least one of status_code or body must be provided."
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
            lambda_function_nested_body, body={"data": {"id": 42}}
        )
        assert result["statusCode"] == 200

    def test_raises_when_nested_value_mismatches(
        self, lambda_client: LambdaClient, lambda_function_nested_body: str
    ) -> None:
        with pytest.raises(LambdaResponseMismatchError):
            expect_lambda(lambda_client).to_respond_with(
                lambda_function_nested_body, body={"data": {"id": 99}}
            )

    def test_full_nested_dict_matches(
        self, lambda_client: LambdaClient, lambda_function_nested_body: str
    ) -> None:
        result = expect_lambda(lambda_client).to_respond_with(
            lambda_function_nested_body,
            body={"data": {"id": 42, "tags": ["a", "b"]}, "meta": {"version": 1}},
        )
        assert result["statusCode"] == 200
