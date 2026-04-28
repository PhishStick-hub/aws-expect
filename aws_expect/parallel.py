from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import TypeVar

from aws_expect.exceptions import AggregateWaitTimeoutError, WaitTimeoutError

T = TypeVar("T")


def expect_all(
    expectations: Sequence[Callable[[], T]],
    *,
    max_workers: int | None = None,
) -> list[T]:
    """Run multiple expectations in parallel and return all results.

    Each expectation is a zero-argument callable that performs a wait
    operation (e.g. ``expect_dynamodb_item(table).to_exist(...)``).
    All expectations are submitted to a thread pool and executed
    concurrently. The function blocks until every expectation has
    either succeeded or raised.

    Args:
        expectations: A sequence of zero-argument callables. Each
            callable should invoke an expectation method and return
            its result.
        max_workers: Maximum number of threads. Defaults to the
            number of expectations so that all run truly in parallel.

    Returns:
        A list of results in the same order as the input expectations.

    Raises:
        AggregateWaitTimeoutError: If one or more expectations raised
            :class:`WaitTimeoutError`. Contains both the individual
            errors and a ``results`` list (with ``None`` for failed
            entries).

    Example::

        from aws_expect import expect_all, expect_dynamodb_item

        results = expect_all([
            lambda: expect_dynamodb_item(users).to_exist(
                key={"pk": "u1"}, timeout=30,
            ),
            lambda: expect_dynamodb_item(orders).to_exist(
                key={"pk": "o1"}, timeout=30,
            ),
        ])
    """
    if not expectations:
        return []

    workers = max_workers if max_workers is not None else len(expectations)

    futures: list[Future[T]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for expectation in expectations:
            futures.append(executor.submit(expectation))

        # Wait for all futures to complete (executor.__exit__ does this).

    # Collect results, preserving order.
    results: list[T | None] = [None] * len(futures)
    errors: list[WaitTimeoutError] = []

    for idx, future in enumerate(futures):
        exc = future.exception()
        if exc is None:
            results[idx] = future.result()
        elif isinstance(exc, WaitTimeoutError):
            errors.append(exc)
        else:
            # Non-WaitTimeoutError exceptions propagate immediately.
            raise exc

    if errors:
        raise AggregateWaitTimeoutError(errors=errors, results=results)

    # At this point every entry is a real T, not None.
    return results  # type: ignore[return-value]


def expect_any(
    expectations: Sequence[Callable[[], T]],
    *,
    max_workers: int | None = None,
) -> T:
    """Run multiple expectations in parallel and return the first to succeed.

    Each expectation is a zero-argument callable that performs a wait
    operation. All expectations are submitted to a thread pool and executed
    concurrently. The function returns the result of whichever callable
    completes successfully first and cancels the remaining callables.

    Args:
        expectations: A sequence of zero-argument callables. Each
            callable should invoke an expectation method and return
            its result.
        max_workers: Maximum number of threads. Defaults to the
            number of expectations so that all run truly in parallel.

    Returns:
        The result of the first callable that succeeds.

    Raises:
        AggregateWaitTimeoutError: If every callable raises
            :class:`WaitTimeoutError` before any succeeds. Contains
            all individual errors and a ``results`` list of ``None``
            entries.
        ValueError: If *expectations* is empty.

    Example::

        from aws_expect import expect_any, expect_dynamodb_item

        result = expect_any([
            lambda: expect_dynamodb_item(table_a).to_exist(
                key={"pk": "u1"}, timeout=30,
            ),
            lambda: expect_dynamodb_item(table_b).to_exist(
                key={"pk": "u1"}, timeout=30,
            ),
        ])
    """
    if not expectations:
        msg = "expectations must not be empty"
        raise ValueError(msg)

    workers = max_workers if max_workers is not None else len(expectations)
    errors: list[WaitTimeoutError] = []
    results: list[T | None] = [None] * len(expectations)

    future_to_idx: dict[Future[T], int] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for idx, expectation in enumerate(expectations):
            future = executor.submit(expectation)
            future_to_idx[future] = idx

        for future in as_completed(future_to_idx):
            exc = future.exception()
            if exc is None:
                # First success — return immediately.
                # ThreadPoolExecutor.__exit__ will wait for remaining threads,
                # but their results are discarded.
                return future.result()
            elif isinstance(exc, WaitTimeoutError):
                errors.append(exc)
            else:
                # Non-WaitTimeoutError propagates immediately.
                raise exc

    # All futures completed with WaitTimeoutError.
    raise AggregateWaitTimeoutError(errors=errors, results=results)
