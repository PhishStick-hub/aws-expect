"""Tests for LambdaFunctionExpectation.to_respond_with."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from mypy_boto3_lambda.client import LambdaClient

from aws_expect import expect_lambda
from aws_expect.exceptions import LambdaResponseMismatchError


class TestToRespondWith:
    def test_returns_payload_when_status_code_matches(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        result = expect_lambda(lambda_client).to_respond_with(
            lambda_function_json_body, status_code=HTTPStatus.OK
        )
        assert result["statusCode"] == HTTPStatus.OK

    def test_returns_payload_when_body_entries_match(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        result = expect_lambda(lambda_client).to_respond_with(
            lambda_function_json_body,
            body={"message": "hello"},
        )
        assert result["statusCode"] == HTTPStatus.OK

    def test_returns_payload_when_both_status_code_and_body_match(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        result = expect_lambda(lambda_client).to_respond_with(
            lambda_function_json_body,
            status_code=HTTPStatus.OK,
            body={"message": "hello", "status": "ok"},
        )
        assert result["statusCode"] == HTTPStatus.OK

    def test_returns_payload_when_neither_specified(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        result = expect_lambda(lambda_client).to_respond_with(lambda_function_json_body)
        assert result["statusCode"] == HTTPStatus.OK

    def test_returns_payload_with_custom_invocation_payload(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        result = expect_lambda(lambda_client).to_respond_with(
            lambda_function_json_body,
            payload={"input": "data"},
            status_code=HTTPStatus.OK,
        )
        assert result["statusCode"] == HTTPStatus.OK

    def test_raises_when_status_code_does_not_match(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        with pytest.raises(LambdaResponseMismatchError) as exc_info:
            expect_lambda(lambda_client).to_respond_with(
                lambda_function_json_body, status_code=HTTPStatus.NOT_FOUND
            )
        assert exc_info.value.function_name == lambda_function_json_body

    def test_raises_when_body_entry_does_not_match(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        with pytest.raises(LambdaResponseMismatchError) as exc_info:
            expect_lambda(lambda_client).to_respond_with(
                lambda_function_json_body,
                body={"nonexistent": "key"},
            )
        assert exc_info.value.function_name == lambda_function_json_body

    def test_raises_when_function_errors(
        self, lambda_client: LambdaClient, error_lambda_function: str
    ) -> None:
        with pytest.raises(LambdaResponseMismatchError) as exc_info:
            expect_lambda(lambda_client).to_respond_with(
                error_lambda_function, status_code=HTTPStatus.OK
            )
        assert exc_info.value.function_name == error_lambda_function

    def test_body_subset_match_ignores_extra_fields(
        self, lambda_client: LambdaClient, lambda_function_json_body: str
    ) -> None:
        # The handler returns {"message": "hello", "status": "ok"} — match on one field only.
        result = expect_lambda(lambda_client).to_respond_with(
            lambda_function_json_body,
            body={"status": "ok"},
        )
        assert result["statusCode"] == HTTPStatus.OK
