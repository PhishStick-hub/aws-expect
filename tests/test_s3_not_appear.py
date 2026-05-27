import threading
import time

import pytest
from mypy_boto3_s3.service_resource import S3ServiceResource

from aws_expect import S3ObjectAppearedError, WaitTimeoutError, expect_s3


class TestToNotAppear:
    """Tests for expect_s3(s3_object).to_not_appear()."""

    def test_returns_none_when_object_stays_absent(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "never-created.txt"

        obj = s3_resource.Object(test_bucket, key)
        result = expect_s3(obj).to_not_appear(timeout=2, poll_interval=1)

        assert result is None

    def test_raises_immediately_when_object_already_exists(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "already-here.txt"
        s3_resource.Object(test_bucket, key).put(Body=b"pre-existing")

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(S3ObjectAppearedError) as exc_info:
            expect_s3(obj).to_not_appear(timeout=10, poll_interval=1)

        assert exc_info.value.bucket == test_bucket
        assert exc_info.value.key == key
        assert exc_info.value.timeout == 10
        assert exc_info.value.metadata["ContentLength"] == len(b"pre-existing")

    def test_raises_when_object_appears_mid_window(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "delayed-upload.txt"

        def upload_later() -> None:
            s3_resource.Object(test_bucket, key).put(Body=b"appeared")

        timer = threading.Timer(2.0, upload_later)
        timer.start()

        try:
            obj = s3_resource.Object(test_bucket, key)
            with pytest.raises(S3ObjectAppearedError) as exc_info:
                expect_s3(obj).to_not_appear(timeout=10, poll_interval=1)

            assert exc_info.value.metadata["ContentLength"] == len(b"appeared")
        finally:
            timer.cancel()

    def test_not_a_wait_timeout_error(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "already-here.txt"
        s3_resource.Object(test_bucket, key).put(Body=b"data")

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(S3ObjectAppearedError) as exc_info:
            expect_s3(obj).to_not_appear(timeout=10, poll_interval=1)

        assert not isinstance(exc_info.value, WaitTimeoutError)

    def test_completes_within_timeout_when_object_never_appears(
        self, s3_resource: S3ServiceResource, test_bucket: str
    ) -> None:
        key = "ghost.txt"

        obj = s3_resource.Object(test_bucket, key)
        start = time.monotonic()
        result = expect_s3(obj).to_not_appear(timeout=3, poll_interval=1)
        elapsed = time.monotonic() - start

        assert result is None
        assert elapsed >= 3.0
