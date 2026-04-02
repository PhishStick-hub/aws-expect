"""Expectation wrapper for AWS Lambda functions."""

from __future__ import annotations

import json
import math
import time
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError, WaiterError

from aws_expect.exceptions import LambdaWaitTimeoutError

if TYPE_CHECKING:
    from mypy_boto3_lambda.client import LambdaClient
    from mypy_boto3_lambda.type_defs import GetFunctionResponseTypeDef


class LambdaFunctionExpectation:
    """Expectation wrapper for a Lambda function using a boto3 Lambda client.

    Lambda has no boto3 resource API, so this class wraps the client directly.
    The function name is passed per method call rather than at construction time,
    allowing one instance to be reused across different functions.
    """

    def __init__(self, lambda_client: LambdaClient) -> None:
        self._client = lambda_client

    def to_exist(
        self,
        function_name: str,
        timeout: float = 30,
        poll_interval: float = 2,
    ) -> GetFunctionResponseTypeDef:
        """Wait for the Lambda function to exist.

        Uses the native ``function_exists`` boto3 waiter.

        Args:
            function_name: Name or ARN of the Lambda function.
            timeout: Maximum time in seconds to wait.
            poll_interval: Time in seconds between polling attempts (minimum 1).

        Returns:
            The ``get_function`` response dict on success.

        Raises:
            LambdaWaitTimeoutError: If the function does not exist within *timeout*.
        """
        waiter_config = self._build_waiter_config(timeout, poll_interval)
        try:
            self._client.get_waiter("function_exists").wait(
                FunctionName=function_name,
                WaiterConfig=waiter_config,
            )
        except WaiterError as exc:
            raise LambdaWaitTimeoutError(function_name, timeout) from exc
        return self._client.get_function(FunctionName=function_name)

    def to_not_exist(
        self,
        function_name: str,
        timeout: float = 30,
        poll_interval: float = 2,
    ) -> None:
        """Wait for the Lambda function to be deleted.

        Uses a custom polling loop (no native waiter for deletion).

        Args:
            function_name: Name or ARN of the Lambda function.
            timeout: Maximum time in seconds to wait.
            poll_interval: Time in seconds between polling attempts (minimum 1).

        Returns:
            None when the function no longer exists.

        Raises:
            LambdaWaitTimeoutError: If the function still exists after *timeout*.
        """
        delay = max(1, math.ceil(poll_interval))
        deadline = time.monotonic() + timeout

        while True:
            try:
                self._client.get_function(FunctionName=function_name)
            except ClientError as exc:
                if exc.response["Error"]["Code"] == "ResourceNotFoundException":
                    return None
                raise

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LambdaWaitTimeoutError(function_name, timeout)
            time.sleep(min(delay, remaining))

    def to_be_active(
        self,
        function_name: str,
        timeout: float = 30,
        poll_interval: float = 2,
    ) -> GetFunctionResponseTypeDef:
        """Wait for the Lambda function to reach the ``Active`` state.

        Uses the native ``function_active_v2`` boto3 waiter which polls
        ``get_function`` and succeeds when ``Configuration.State == "Active"``.

        Args:
            function_name: Name or ARN of the Lambda function.
            timeout: Maximum time in seconds to wait.
            poll_interval: Time in seconds between polling attempts (minimum 1).

        Returns:
            The ``get_function`` response dict when state is ``Active``.

        Raises:
            LambdaWaitTimeoutError: If the function does not reach ``Active``
                within *timeout*, or if it enters the ``Failed`` state.
        """
        waiter_config = self._build_waiter_config(timeout, poll_interval)
        try:
            self._client.get_waiter("function_active_v2").wait(
                FunctionName=function_name,
                WaiterConfig=waiter_config,
            )
        except WaiterError as exc:
            raise LambdaWaitTimeoutError(function_name, timeout) from exc
        return self._client.get_function(FunctionName=function_name)

    def to_be_updated(
        self,
        function_name: str,
        timeout: float = 30,
        poll_interval: float = 2,
    ) -> GetFunctionResponseTypeDef:
        """Wait for the Lambda function's last update to complete successfully.

        Uses the native ``function_updated_v2`` boto3 waiter which polls
        ``get_function`` and succeeds when
        ``Configuration.LastUpdateStatus == "Successful"``.

        Args:
            function_name: Name or ARN of the Lambda function.
            timeout: Maximum time in seconds to wait.
            poll_interval: Time in seconds between polling attempts (minimum 1).

        Returns:
            The ``get_function`` response dict when ``LastUpdateStatus`` is
            ``Successful``.

        Raises:
            LambdaWaitTimeoutError: If the update does not complete within
                *timeout*, or if ``LastUpdateStatus`` becomes ``Failed``.
        """
        waiter_config = self._build_waiter_config(timeout, poll_interval)
        try:
            self._client.get_waiter("function_updated_v2").wait(
                FunctionName=function_name,
                WaiterConfig=waiter_config,
            )
        except WaiterError as exc:
            raise LambdaWaitTimeoutError(function_name, timeout) from exc
        return self._client.get_function(FunctionName=function_name)

    def to_be_invocable(
        self,
        function_name: str,
        timeout: float = 30,
        poll_interval: float = 2,
        payload: dict[str, Any] | None = None,
        entries: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Wait for the Lambda function to be successfully invocable.

        Invokes the function on each poll attempt. Succeeds when the invocation
        returns no ``FunctionError`` and, if *entries* is provided, the parsed
        response payload contains all expected key-value pairs (subset match).

        Args:
            function_name: Name or ARN of the Lambda function.
            timeout: Maximum time in seconds to wait.
            poll_interval: Time in seconds between polling attempts (minimum 1).
            payload: Optional dict to send as the invocation event (JSON-serialized).
            entries: Optional dict of expected key-value pairs to match against
                the parsed response payload (subset match).

        Returns:
            The parsed response payload dict on success.

        Raises:
            LambdaWaitTimeoutError: If the function does not become invocable
                (or does not match *entries*) within *timeout*.
        """
        delay = max(1, math.ceil(poll_interval))
        deadline = time.monotonic() + timeout

        invoke_kwargs: dict[str, Any] = {"FunctionName": function_name}
        if payload is not None:
            invoke_kwargs["Payload"] = json.dumps(payload).encode()

        while True:
            response = self._client.invoke(**invoke_kwargs)
            if not response.get("FunctionError"):
                response_payload: dict[str, Any] = json.loads(
                    response["Payload"].read()
                )
                if entries is None or self._matches_entries(response_payload, entries):
                    return response_payload

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LambdaWaitTimeoutError(function_name, timeout)
            time.sleep(min(delay, remaining))

    @staticmethod
    def _build_waiter_config(timeout: float, poll_interval: float) -> dict[str, int]:
        """Convert timeout/poll_interval into a botocore WaiterConfig dict."""
        delay = max(1, math.ceil(poll_interval))
        max_attempts = max(1, math.ceil(timeout / delay))
        return {"Delay": delay, "MaxAttempts": max_attempts}

    @staticmethod
    def _matches_entries(data: dict[str, Any], entries: dict[str, Any]) -> bool:
        """Check that *data* contains all expected *entries* (shallow subset match)."""
        return all(data.get(k) == v for k, v in entries.items())
