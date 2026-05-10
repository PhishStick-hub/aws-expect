"""Tests for _truncate_value helper function."""

from __future__ import annotations

import pytest

from aws_expect._utils import _truncate_value


class TestTruncateValue:
    """Tests for _truncate_value truncation behavior."""

    def test_none_returns_string_none(self) -> None:
        """None input returns the string 'None'."""
        result = _truncate_value(None)
        assert result == "None"

    def test_small_list_no_truncation(self) -> None:
        """Lists with <= 50 items are not truncated."""
        result = _truncate_value([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_large_list_truncated_at_50(self) -> None:
        """Lists with > 50 items are truncated with count annotation."""
        value = list(range(100))
        result = _truncate_value(value)
        # Should show first 50 items via repr
        expected_prefix = repr(value[:50])
        assert result.startswith(expected_prefix)
        assert "... (50 more items not shown)" in result

    def test_short_string_no_truncation(self) -> None:
        """Values with repr <= 500 chars are not truncated."""
        result = _truncate_value("short")
        assert result == "'short'"

    def test_long_string_truncated_at_500(self) -> None:
        """Values with repr > 500 chars are truncated with char count."""
        value = "x" * 1000
        result = _truncate_value(value)
        total_len = len(repr(value))
        # Should start with first 500 chars of repr
        assert result.startswith(repr(value)[:500])
        assert f"... (value truncated, showing first 500 of {total_len} chars)" in result

    def test_tuple_treated_like_list(self) -> None:
        """Tuples follow the same truncation rules as lists."""
        result = _truncate_value((1, 2))
        assert result == "(1, 2)"

    def test_short_int_no_truncation(self) -> None:
        """Non-collection values with short repr are returned as-is."""
        result = _truncate_value(42)
        assert result == "42"

    def test_short_dict_no_truncation(self) -> None:
        """Dicts with short repr are returned as-is."""
        result = _truncate_value({"key": "value"})
        assert result == "{'key': 'value'}"
