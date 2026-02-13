import threading

import pytest

from aws_expect import S3WaitTimeoutError, expect_s3


class TestToNotExist:
    """Tests for expect_s3(s3_object).to_not_exist()."""

    def test_returns_none_when_object_absent(self, s3_resource, test_bucket):
        key = "ghost.txt"

        obj = s3_resource.Object(test_bucket, key)
        result = expect_s3(obj).to_not_exist(timeout=10, poll_interval=1)

        assert result is None

    def test_raises_timeout_when_object_still_exists(
        self, s3_client, s3_resource, test_bucket
    ):
        key = "persistent.txt"
        s3_client.put_object(Bucket=test_bucket, Key=key, Body=b"still here")

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(S3WaitTimeoutError) as exc_info:
            expect_s3(obj).to_not_exist(timeout=2, poll_interval=1)

        assert exc_info.value.bucket == test_bucket
        assert exc_info.value.key == key
        assert exc_info.value.timeout == 2

    def test_succeeds_when_object_deleted_mid_poll(
        self, s3_client, s3_resource, test_bucket
    ):
        key = "temporary.txt"
        s3_client.put_object(Bucket=test_bucket, Key=key, Body=b"going away")

        def delete_later():
            s3_client.delete_object(Bucket=test_bucket, Key=key)

        timer = threading.Timer(2.0, delete_later)
        timer.start()

        try:
            obj = s3_resource.Object(test_bucket, key)
            result = expect_s3(obj).to_not_exist(timeout=10, poll_interval=1)
            assert result is None
        finally:
            timer.cancel()
