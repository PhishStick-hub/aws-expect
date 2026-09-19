"""Tests for _check_stop_condition reason semantics."""

from __future__ import annotations

import re
import time
from typing import Any

import pytest

from aws_expect._utils import _check_stop_condition
from aws_expect.exceptions import StopConditionMetError


def _raised_by(result: Any, resource_id: str = "res") -> StopConditionMetError:
    """Run _check_stop_condition with a constant-returning predicate."""
    with pytest.raises(StopConditionMetError) as exc_info:
        _check_stop_condition(
            {"status": "pending"},
            lambda state: result,
            resource_id,
            time.monotonic(),
            5.0,
        )
    return exc_info.value


class TestCheckStopConditionReasons:
    """Pins the reason semantics declared in _check_stop_condition."""

    def test_string_result_becomes_stop_reason(self) -> None:
        err = _raised_by("why")
        assert err.stop_reason == "why"
        assert str(err).endswith(": 'why'")

    def test_dict_result_becomes_stop_reason(self) -> None:
        err = _raised_by({"code": 500})
        assert err.stop_reason == {"code": 500}
        assert str(err).endswith(": {'code': 500}")

    def test_bare_true_gives_no_reason(self) -> None:
        err = _raised_by(True)
        assert err.stop_reason is None

    def test_non_str_dict_truthy_result_gives_no_reason(self) -> None:
        """A truthy value that is not str/dict stops with stop_reason None."""
        err = _raised_by(1)
        assert err.stop_reason is None
        assert re.fullmatch(r"Stop condition met for 'res' after \d+\.\d+s", str(err))

    def test_falsy_result_returns_none(self) -> None:
        result = _check_stop_condition(
            {"status": "pending"}, lambda state: False, "res", time.monotonic(), 5.0
        )
        assert result is None

    def test_none_predicate_is_no_op(self) -> None:
        result = _check_stop_condition(
            {"status": "pending"}, None, "res", time.monotonic(), 5.0
        )
        assert result is None
