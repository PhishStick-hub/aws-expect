import json
import threading

import pytest

from aws_expect import S3WaitTimeoutError, expect_s3


class TestToExist:
    """Tests for expect_s3(s3_object).to_exist()."""

    def test_returns_metadata_when_object_exists(
        self, s3_client, s3_resource, test_bucket
    ):
        key = "hello.txt"
        s3_client.put_object(Bucket=test_bucket, Key=key, Body=b"hello world")

        obj = s3_resource.Object(test_bucket, key)
        result = expect_s3(obj).to_exist(timeout=10, poll_interval=1)

        assert result["ContentLength"] == len(b"hello world")
        assert "ETag" in result
        assert "LastModified" in result
        assert "ContentType" in result

    def test_raises_timeout_when_object_missing(self, s3_resource, test_bucket):
        key = "does-not-exist.txt"

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(S3WaitTimeoutError) as exc_info:
            expect_s3(obj).to_exist(timeout=2, poll_interval=1)

        assert exc_info.value.bucket == test_bucket
        assert exc_info.value.key == key
        assert exc_info.value.timeout == 2

    def test_succeeds_when_object_appears_mid_poll(
        self, s3_client, s3_resource, test_bucket
    ):
        key = "delayed.txt"

        def upload_later():
            s3_client.put_object(Bucket=test_bucket, Key=key, Body=b"arrived")

        timer = threading.Timer(2.0, upload_later)
        timer.start()

        try:
            obj = s3_resource.Object(test_bucket, key)
            result = expect_s3(obj).to_exist(timeout=10, poll_interval=1)
            assert result["ContentLength"] == len(b"arrived")
        finally:
            timer.cancel()

    def test_returns_correct_metadata_for_content_type(
        self, s3_client, s3_resource, test_bucket
    ):
        key = "data.json"
        s3_client.put_object(
            Bucket=test_bucket,
            Key=key,
            Body=b'{"a": 1}',
            ContentType="application/json",
        )

        obj = s3_resource.Object(test_bucket, key)
        result = expect_s3(obj).to_exist(timeout=10, poll_interval=1)

        assert result["ContentType"] == "application/json"

    def test_matches_expected_entries(self, s3_client, s3_resource, test_bucket):
        key = "order.json"
        s3_client.put_object(
            Bucket=test_bucket,
            Key=key,
            Body=json.dumps({"status": "active", "total": 100}).encode(),
        )

        obj = s3_resource.Object(test_bucket, key)
        result = expect_s3(obj).to_exist(
            entries={"status": "active"},
            timeout=10,
            poll_interval=1,
        )

        assert result["status"] == "active"
        assert result["total"] == 100  # extra fields are present

    def test_raises_timeout_when_entries_dont_match(
        self, s3_client, s3_resource, test_bucket
    ):
        key = "order.json"
        s3_client.put_object(
            Bucket=test_bucket,
            Key=key,
            Body=json.dumps({"status": "pending"}).encode(),
        )

        obj = s3_resource.Object(test_bucket, key)
        with pytest.raises(S3WaitTimeoutError):
            expect_s3(obj).to_exist(
                entries={"status": "shipped"},
                timeout=2,
                poll_interval=1,
            )

    def test_succeeds_when_entries_match_after_update(
        self, s3_client, s3_resource, test_bucket
    ):
        key = "order.json"
        s3_client.put_object(
            Bucket=test_bucket,
            Key=key,
            Body=json.dumps({"status": "pending"}).encode(),
        )

        def update_later():
            s3_client.put_object(
                Bucket=test_bucket,
                Key=key,
                Body=json.dumps({"status": "shipped"}).encode(),
            )

        timer = threading.Timer(2.0, update_later)
        timer.start()

        try:
            obj = s3_resource.Object(test_bucket, key)
            result = expect_s3(obj).to_exist(
                entries={"status": "shipped"},
                timeout=10,
                poll_interval=1,
            )
            assert result["status"] == "shipped"
        finally:
            timer.cancel()
