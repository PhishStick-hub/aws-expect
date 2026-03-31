"""Tests for LambdaFunctionExpectation: to_exist, to_not_exist, to_be_active, to_be_updated."""

from __future__ import annotations

import threading

import pytest
from mypy_boto3_lambda.client import LambdaClient

from aws_expect import WaitTimeoutError, expect_lambda
from aws_expect.exceptions import LambdaWaitTimeoutError


class TestToExist:
    def test_returns_response_when_function_exists(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        result = expect_lambda(lambda_client).to_exist(
            lambda_function, timeout=10, poll_interval=1
        )
        assert result["Configuration"]["FunctionName"] == lambda_function

    def test_raises_when_function_missing(self, lambda_client: LambdaClient) -> None:
        with pytest.raises(LambdaWaitTimeoutError) as exc_info:
            expect_lambda(lambda_client).to_exist(
                "nonexistent-fn", timeout=2, poll_interval=1
            )
        assert exc_info.value.function_name == "nonexistent-fn"
        assert exc_info.value.timeout == 2

    def test_catchable_as_wait_timeout_error(self, lambda_client: LambdaClient) -> None:
        with pytest.raises(WaitTimeoutError):
            expect_lambda(lambda_client).to_exist(
                "nonexistent-fn", timeout=2, poll_interval=1
            )


class TestToNotExist:
    def test_returns_none_after_function_deleted(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        lambda_client.delete_function(FunctionName=lambda_function)
        result = expect_lambda(lambda_client).to_not_exist(
            lambda_function, timeout=10, poll_interval=1
        )
        assert result is None

    def test_raises_when_function_still_exists(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        with pytest.raises(LambdaWaitTimeoutError) as exc_info:
            expect_lambda(lambda_client).to_not_exist(
                lambda_function, timeout=2, poll_interval=1
            )
        assert exc_info.value.function_name == lambda_function
        assert exc_info.value.timeout == 2

    def test_catchable_as_wait_timeout_error(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        with pytest.raises(WaitTimeoutError):
            expect_lambda(lambda_client).to_not_exist(
                lambda_function, timeout=2, poll_interval=1
            )

    def test_succeeds_when_function_deleted_mid_poll(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        def delete_later() -> None:
            lambda_client.delete_function(FunctionName=lambda_function)

        timer = threading.Timer(2.0, delete_later)
        timer.start()
        try:
            result = expect_lambda(lambda_client).to_not_exist(
                lambda_function, timeout=15, poll_interval=1
            )
            assert result is None
        finally:
            timer.cancel()


class TestToBeActive:
    def test_returns_response_when_function_active(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        result = expect_lambda(lambda_client).to_be_active(
            lambda_function, timeout=10, poll_interval=1
        )
        assert result["Configuration"]["State"] == "Active"

    def test_raises_when_function_missing(self, lambda_client: LambdaClient) -> None:
        with pytest.raises(LambdaWaitTimeoutError) as exc_info:
            expect_lambda(lambda_client).to_be_active(
                "nonexistent-fn", timeout=2, poll_interval=1
            )
        assert exc_info.value.function_name == "nonexistent-fn"
        assert exc_info.value.timeout == 2

    def test_catchable_as_wait_timeout_error(self, lambda_client: LambdaClient) -> None:
        with pytest.raises(WaitTimeoutError):
            expect_lambda(lambda_client).to_be_active(
                "nonexistent-fn", timeout=2, poll_interval=1
            )


class TestToBeUpdated:
    def test_returns_response_when_update_successful(
        self, lambda_client: LambdaClient, lambda_function: str
    ) -> None:
        result = expect_lambda(lambda_client).to_be_updated(
            lambda_function, timeout=10, poll_interval=1
        )
        assert result["Configuration"]["LastUpdateStatus"] == "Successful"

    def test_raises_when_function_missing(self, lambda_client: LambdaClient) -> None:
        with pytest.raises(LambdaWaitTimeoutError) as exc_info:
            expect_lambda(lambda_client).to_be_updated(
                "nonexistent-fn", timeout=2, poll_interval=1
            )
        assert exc_info.value.function_name == "nonexistent-fn"
        assert exc_info.value.timeout == 2

    def test_catchable_as_wait_timeout_error(self, lambda_client: LambdaClient) -> None:
        with pytest.raises(WaitTimeoutError):
            expect_lambda(lambda_client).to_be_updated(
                "nonexistent-fn", timeout=2, poll_interval=1
            )
