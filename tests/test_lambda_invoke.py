"""Tests for LambdaFunctionExpectation.to_be_invocable."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from mypy_boto3_lambda.client import LambdaClient

from aws_expect import WaitTimeoutError, expect_lambda
from aws_expect.exceptions import LambdaWaitTimeoutError


class TestToBeInvocable:
    def test_returns_payload_without_arguments(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        result = expect_lambda(lambda_client).to_be_invocable(
            lambda_function, timeout=10, poll_interval=1
        )
        assert result["statusCode"] == HTTPStatus.OK

    def test_returns_payload_with_event_payload(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        result = expect_lambda(lambda_client).to_be_invocable(
            lambda_function,
            timeout=10,
            poll_interval=1,
            payload={"key": "value"},
        )
        assert result["statusCode"] == HTTPStatus.OK

    def test_succeeds_with_matching_entries(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        result = expect_lambda(lambda_client).to_be_invocable(
            lambda_function,
            timeout=10,
            poll_interval=1,
            entries={"statusCode": HTTPStatus.OK},
        )
        assert result["statusCode"] == HTTPStatus.OK

    def test_raises_when_entries_do_not_match(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        with pytest.raises(LambdaWaitTimeoutError) as exc_info:
            expect_lambda(lambda_client).to_be_invocable(
                lambda_function,
                timeout=2,
                poll_interval=1,
                entries={"statusCode": 999},
            )
        assert exc_info.value.function_name == lambda_function
        assert exc_info.value.timeout == 2

    def test_raises_when_handler_errors(
        self, lambda_client: LambdaClient, error_lambda_function: str
    ) -> None:
        with pytest.raises(LambdaWaitTimeoutError) as exc_info:
            expect_lambda(lambda_client).to_be_invocable(
                error_lambda_function, timeout=2, poll_interval=1
            )
        assert exc_info.value.function_name == error_lambda_function

    def test_catchable_as_wait_timeout_error(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        with pytest.raises(WaitTimeoutError):
            expect_lambda(lambda_client).to_be_invocable(
                lambda_function,
                timeout=2,
                poll_interval=1,
                entries={"statusCode": 999},
            )

    def test_raises_when_function_missing(self, lambda_client: LambdaClient) -> None:
        with pytest.raises(Exception):
            expect_lambda(lambda_client).to_be_invocable(
                "nonexistent-fn", timeout=2, poll_interval=1
            )
