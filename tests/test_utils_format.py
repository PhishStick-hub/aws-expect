"""Tests for _format_timeout_error helper function."""

from __future__ import annotations

from aws_expect._utils import _format_timeout_error


class TestFormatTimeoutError:
    """Tests for _format_timeout_error message formatting."""

    def test_both_none_no_sections(self) -> None:
        """When both expected and actual are None, only the first line is shown."""
        result = _format_timeout_error(
            resource_desc="my-resource",
            expected=None,
            actual=None,
            timeout=10.0,
        )
        lines = result.split("\n")
        assert len(lines) == 1
        assert "Timed out after 10.0s waiting for my-resource" in result
        assert "Expected:" not in result
        assert "Actual:" not in result

    def test_only_expected_present(self) -> None:
        """When only expected is set, only the Expected: section appears."""
        result = _format_timeout_error(
            resource_desc="my-resource",
            expected={"key": "val"},
            actual=None,
            timeout=10.0,
        )
        assert "Expected:" in result
        assert "Actual:" not in result
        assert "Timed out after 10.0s waiting for my-resource" in result

    def test_only_actual_present(self) -> None:
        """When only actual is set, only the Actual: section appears."""
        result = _format_timeout_error(
            resource_desc="my-resource",
            expected=None,
            actual={"key": "val"},
            timeout=10.0,
        )
        assert "Actual:" in result
        assert "Expected:" not in result
        assert "Timed out after 10.0s waiting for my-resource" in result

    def test_both_present_shows_both_sections(self) -> None:
        """When both are set, both sections appear separated by a blank line."""
        result = _format_timeout_error(
            resource_desc="my-resource",
            expected={"a": 1},
            actual={"b": 2},
            timeout=10.0,
        )
        assert "Expected:" in result
        assert "Actual:" in result
        assert "Timed out after 10.0s waiting for my-resource" in result

    def test_large_expected_truncated(self) -> None:
        """Large expected values are truncated via _truncate_value."""
        result = _format_timeout_error(
            resource_desc="my-resource",
            expected=list(range(100)),
            actual=None,
            timeout=10.0,
        )
        assert "... (50 more items not shown)" in result

    def test_timeout_includes_seconds_suffix(self) -> None:
        """The timeout value appears with 's' suffix in the message."""
        result = _format_timeout_error(
            resource_desc="my-resource",
            expected=None,
            actual=None,
            timeout=30.5,
        )
        assert "30.5s" in result

    def test_resource_desc_included_in_message(self) -> None:
        """The resource description appears in the timeout message."""
        result = _format_timeout_error(
            resource_desc="s3://my-bucket/key",
            expected=None,
            actual=None,
            timeout=10.0,
        )
        assert "s3://my-bucket/key" in result
