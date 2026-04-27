import json
import threading
import time

import pytest
from mypy_boto3_s3.service_resource import S3ServiceResource

from aws_expect import (
    S3ContentWaitTimeoutError,
    S3UnexpectedContentError,
    S3WaitTimeoutError,
    WaitTimeoutError,
    expect_s3,
)


class TestS3ToHaveContent:
    """Tests for expect_s3(s3_object).to_have_content(entries=...)."""

    def test_returns_body_on_exact_match(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "content.json"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "ok"}).encode()
        )

        obj = s3_resource.Object(test_bucket, key)
        result = expect_s3(obj).to_have_content(
            {"status": "ok"}, timeout=10, poll_interval=1
        )

        assert result == {"status": "ok"}

    def test_matches_subset_dict(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "content.json"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "ok", "extra": "field"}).encode()
        )

        obj = s3_resource.Object(test_bucket, key)
        result = expect_s3(obj).to_have_content(
            {"status": "ok"}, timeout=10, poll_interval=1
        )

        assert result["extra"] == "field"

    def test_deep_nested_match(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "content.json"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"outer": {"inner": "value", "other": 99}}).encode()
        )

        obj = s3_resource.Object(test_bucket, key)
        result = expect_s3(obj).to_have_content(
            {"outer": {"inner": "value"}}, timeout=10, poll_interval=1
        )

        assert result["outer"]["other"] == 99

    def test_succeeds_when_object_appears_mid_poll(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "delayed.json"

        def upload_later() -> None:
            s3_resource.Object(test_bucket, key).put(
                Body=json.dumps({"status": "ready"}).encode()
            )

        timer = threading.Timer(2.0, upload_later)
        timer.start()

        try:
            obj = s3_resource.Object(test_bucket, key)
            result = expect_s3(obj).to_have_content(
                {"status": "ready"}, timeout=10, poll_interval=1
            )
            assert result["status"] == "ready"
        finally:
            timer.cancel()

    def test_raises_timeout_when_no_match(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "content.json"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "wrong"}).encode()
        )

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(S3ContentWaitTimeoutError):
            expect_s3(obj).to_have_content(
                {"status": "right"}, timeout=2, poll_interval=1
            )

    def test_timeout_error_stores_expected_and_actual(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "content.json"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "wrong"}).encode()
        )

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(S3ContentWaitTimeoutError) as exc_info:
            expect_s3(obj).to_have_content(
                {"status": "right"}, timeout=2, poll_interval=1
            )

        assert exc_info.value.expected == {"status": "right"}
        assert exc_info.value.actual == {"status": "wrong"}
        assert exc_info.value.bucket == test_bucket
        assert exc_info.value.key == key
        assert exc_info.value.timeout == 2

    def test_catchable_as_s3_wait_timeout_error(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "content.json"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "wrong"}).encode()
        )

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(S3WaitTimeoutError) as exc_info:
            expect_s3(obj).to_have_content(
                {"status": "right"}, timeout=2, poll_interval=1
            )

        assert isinstance(exc_info.value, S3WaitTimeoutError)

    def test_catchable_as_wait_timeout_error(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "content.json"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "wrong"}).encode()
        )

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(WaitTimeoutError) as exc_info:
            expect_s3(obj).to_have_content(
                {"status": "right"}, timeout=2, poll_interval=1
            )

        assert isinstance(exc_info.value, WaitTimeoutError)

    def test_non_json_body_skipped(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "content.json"
        s3_resource.Object(test_bucket, key).put(Body=b"not json")

        def replace_with_json() -> None:
            s3_resource.Object(test_bucket, key).put(
                Body=json.dumps({"status": "done"}).encode()
            )

        timer = threading.Timer(2.0, replace_with_json)
        timer.start()

        try:
            obj = s3_resource.Object(test_bucket, key)
            result = expect_s3(obj).to_have_content(
                {"status": "done"}, timeout=10, poll_interval=1
            )
            assert result["status"] == "done"
        finally:
            timer.cancel()


class TestS3ToNotHaveContent:
    """Tests for expect_s3(s3_object).to_not_have_content(entries=...)."""

    def test_returns_none_when_object_missing(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "missing.json"
        obj = s3_resource.Object(test_bucket, key)

        result = expect_s3(obj).to_not_have_content({"x": 1}, delay=0)

        assert result is None

    def test_returns_none_when_no_match(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "content.json"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "ok"}).encode()
        )

        obj = s3_resource.Object(test_bucket, key)
        result = expect_s3(obj).to_not_have_content({"status": "different"}, delay=0)

        assert result is None

    def test_raises_when_content_matches(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "content.json"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "present"}).encode()
        )

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(S3UnexpectedContentError):
            expect_s3(obj).to_not_have_content({"status": "present"}, delay=0)

    def test_error_stores_context_fields(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "content.json"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "present"}).encode()
        )

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(S3UnexpectedContentError) as exc_info:
            expect_s3(obj).to_not_have_content({"status": "present"}, delay=0)

        assert exc_info.value.bucket == test_bucket
        assert exc_info.value.key == key
        assert exc_info.value.entries == {"status": "present"}
        assert exc_info.value.delay == 0

    def test_not_a_wait_timeout_error(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "content.json"
        s3_resource.Object(test_bucket, key).put(
            Body=json.dumps({"status": "present"}).encode()
        )

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(S3UnexpectedContentError) as exc_info:
            expect_s3(obj).to_not_have_content({"status": "present"}, delay=0)

        assert not isinstance(exc_info.value, WaitTimeoutError)

    def test_delay_zero_clamped_to_one_second(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "missing.json"
        obj = s3_resource.Object(test_bucket, key)

        start = time.monotonic()
        result = expect_s3(obj).to_not_have_content({"x": 1}, delay=0)
        elapsed = time.monotonic() - start

        assert result is None
        assert elapsed >= 1.0

    def test_non_json_body_treated_as_non_match(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "content.txt"
        s3_resource.Object(test_bucket, key).put(Body=b"not json")

        obj = s3_resource.Object(test_bucket, key)
        result = expect_s3(obj).to_not_have_content({"x": 1}, delay=0)

        assert result is None
