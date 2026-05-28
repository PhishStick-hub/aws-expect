import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from mypy_boto3_dynamodb.service_resource import Table

from aws_expect import (
    DynamoDBInvalidTimestampError,
    DynamoDBWaitTimeoutError,
    WaitTimeoutError,
    expect_dynamodb_item,
)


class TestToHaveDatetimeCloseTo:
    """Tests for expect_dynamodb_item(table).to_have_datetime_close_to(...)."""

    def test_returns_item_when_epoch_decimal_within_delta(
        self, dynamodb_table: Table
    ) -> None:
        now = datetime.now(timezone.utc)
        dynamodb_table.put_item(
            Item={"pk": "item-1", "created_at": Decimal(str(now.timestamp()))}
        )

        result = expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
            key={"pk": "item-1"},
            field="created_at",
            delta=timedelta(seconds=10),
            expected=now,
            timeout=10,
            poll_interval=1,
        )

        assert result["pk"] == "item-1"

    def test_returns_item_when_epoch_int_within_delta(
        self, dynamodb_table: Table
    ) -> None:
        now = datetime.now(timezone.utc)
        dynamodb_table.put_item(
            Item={"pk": "item-int", "created_at": int(now.timestamp())}
        )

        result = expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
            key={"pk": "item-int"},
            field="created_at",
            delta=timedelta(seconds=10),
            expected=now,
            timeout=10,
            poll_interval=1,
        )

        assert result["pk"] == "item-int"

    def test_returns_item_when_iso_string_within_delta(
        self, dynamodb_table: Table
    ) -> None:
        now = datetime.now(timezone.utc)
        dynamodb_table.put_item(Item={"pk": "item-2", "created_at": now.isoformat()})

        result = expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
            key={"pk": "item-2"},
            field="created_at",
            delta=timedelta(seconds=10),
            expected=now,
            timeout=10,
            poll_interval=1,
        )

        assert result["pk"] == "item-2"

    def test_returns_item_when_iso_string_with_tz_within_delta(
        self, dynamodb_table: Table
    ) -> None:
        offset = timezone(timedelta(hours=5))
        stored = datetime(2025, 6, 1, 12, 0, 0, tzinfo=offset)
        expected_utc = datetime(2025, 6, 1, 7, 0, 0, tzinfo=timezone.utc)

        dynamodb_table.put_item(
            Item={"pk": "item-tz", "created_at": stored.isoformat()}
        )

        result = expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
            key={"pk": "item-tz"},
            field="created_at",
            delta=timedelta(seconds=1),
            expected=expected_utc,
            timeout=10,
            poll_interval=1,
        )

        assert result["pk"] == "item-tz"

    def test_naive_iso_string_treated_as_utc(self, dynamodb_table: Table) -> None:
        naive_str = "2025-06-01T12:00:00"
        expected = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        dynamodb_table.put_item(Item={"pk": "item-naive", "created_at": naive_str})

        result = expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
            key={"pk": "item-naive"},
            field="created_at",
            delta=timedelta(seconds=1),
            expected=expected,
            timeout=10,
            poll_interval=1,
        )

        assert result["pk"] == "item-naive"

    def test_defaults_expected_to_now(self, dynamodb_table: Table) -> None:
        now = datetime.now(timezone.utc)
        dynamodb_table.put_item(Item={"pk": "item-now", "created_at": now.isoformat()})

        result = expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
            key={"pk": "item-now"},
            field="created_at",
            delta=timedelta(seconds=10),
            timeout=10,
            poll_interval=1,
        )

        assert result["pk"] == "item-now"

    def test_raises_timeout_when_value_out_of_delta(
        self, dynamodb_table: Table
    ) -> None:
        old = datetime(2020, 1, 1, tzinfo=timezone.utc)
        dynamodb_table.put_item(Item={"pk": "item-old", "created_at": old.isoformat()})

        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
                key={"pk": "item-old"},
                field="created_at",
                delta=timedelta(seconds=5),
                expected=datetime(2025, 6, 1, tzinfo=timezone.utc),
                timeout=2,
                poll_interval=1,
            )

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.key == {"pk": "item-old"}
        assert exc_info.value.timeout == 2
        assert "Actual (last seen):" in str(exc_info.value)

    def test_raises_timeout_when_item_missing(self, dynamodb_table: Table) -> None:
        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
                key={"pk": "ghost"},
                field="created_at",
                delta=timedelta(seconds=5),
                timeout=2,
                poll_interval=1,
            )

        assert exc_info.value.actual is None

    def test_raises_timeout_when_field_absent(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(Item={"pk": "item-nofield", "other": "value"})

        with pytest.raises(DynamoDBWaitTimeoutError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
                key={"pk": "item-nofield"},
                field="created_at",
                delta=timedelta(seconds=5),
                timeout=2,
                poll_interval=1,
            )

        assert exc_info.value.actual == {"pk": "item-nofield", "other": "value"}

    def test_raises_immediately_when_field_is_list(self, dynamodb_table: Table) -> None:
        dynamodb_table.put_item(
            Item={"pk": "item-bad", "created_at": ["not", "a", "timestamp"]}
        )

        with pytest.raises(DynamoDBInvalidTimestampError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
                key={"pk": "item-bad"},
                field="created_at",
                delta=timedelta(seconds=5),
                timeout=10,
                poll_interval=1,
            )

        assert exc_info.value.table_name == dynamodb_table.name
        assert exc_info.value.field == "created_at"
        assert exc_info.value.value == ["not", "a", "timestamp"]

    def test_raises_immediately_when_field_is_unparseable_string(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-badstr", "created_at": "not-a-date"})

        with pytest.raises(DynamoDBInvalidTimestampError) as exc_info:
            expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
                key={"pk": "item-badstr"},
                field="created_at",
                delta=timedelta(seconds=5),
                timeout=10,
                poll_interval=1,
            )

        assert exc_info.value.value == "not-a-date"

    def test_catchable_as_base_wait_timeout_error(self, dynamodb_table: Table) -> None:
        with pytest.raises(WaitTimeoutError):
            expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
                key={"pk": "ghost"},
                field="created_at",
                delta=timedelta(seconds=5),
                timeout=2,
                poll_interval=1,
            )

    def test_succeeds_when_timestamp_converges_mid_poll(
        self, dynamodb_table: Table
    ) -> None:
        old = datetime(2020, 1, 1, tzinfo=timezone.utc)
        dynamodb_table.put_item(Item={"pk": "item-conv", "created_at": old.isoformat()})

        def update_later() -> None:
            now = datetime.now(timezone.utc)
            dynamodb_table.update_item(
                Key={"pk": "item-conv"},
                UpdateExpression="SET created_at = :val",
                ExpressionAttributeValues={":val": now.isoformat()},
            )

        timer = threading.Timer(2.0, update_later)
        timer.start()

        try:
            result = expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
                key={"pk": "item-conv"},
                field="created_at",
                delta=timedelta(seconds=10),
                timeout=15,
                poll_interval=1,
            )
            assert result["pk"] == "item-conv"
        finally:
            timer.cancel()

    def test_works_with_composite_key(self, dynamodb_composite_table: Table) -> None:
        now = datetime.now(timezone.utc)
        dynamodb_composite_table.put_item(
            Item={
                "pk": "user-1",
                "sk": "order-1",
                "created_at": Decimal(str(now.timestamp())),
            }
        )

        result = expect_dynamodb_item(
            dynamodb_composite_table
        ).to_have_datetime_close_to(
            key={"pk": "user-1", "sk": "order-1"},
            field="created_at",
            delta=timedelta(seconds=10),
            expected=now,
            timeout=10,
            poll_interval=1,
        )

        assert result["pk"] == "user-1"
        assert result["sk"] == "order-1"

    def test_naive_expected_treated_as_utc(self, dynamodb_table: Table) -> None:
        naive_expected = datetime(2025, 6, 1, 12, 0, 0)
        dynamodb_table.put_item(
            Item={"pk": "item-naive-exp", "created_at": "2025-06-01T12:00:00+00:00"}
        )

        result = expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
            key={"pk": "item-naive-exp"},
            field="created_at",
            delta=timedelta(seconds=1),
            expected=naive_expected,
            timeout=10,
            poll_interval=1,
        )

        assert result["pk"] == "item-naive-exp"

    def test_raises_immediately_when_field_is_boolean(
        self, dynamodb_table: Table
    ) -> None:
        dynamodb_table.put_item(Item={"pk": "item-bool", "created_at": True})

        with pytest.raises(DynamoDBInvalidTimestampError):
            expect_dynamodb_item(dynamodb_table).to_have_datetime_close_to(
                key={"pk": "item-bool"},
                field="created_at",
                delta=timedelta(seconds=5),
                timeout=10,
                poll_interval=1,
            )
