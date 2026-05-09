# Phase 7 Research: S3 Smart Polling

**Phase:** 07 — s3-smart-polling
**Researched:** 2026-05-09
**Confidence:** HIGH

## Executive Summary

Phase 7 adds a `stop_when` predicate parameter to `S3ObjectExpectation.to_exist(entries=...)` — the custom-entry polling path. The predicate receives a shallow-copied resource state dict and can return `True` or a string reason to abort polling early via `StopConditionMetError` (already implemented in Phase 6).

**Key finding:** Phase 6 exceptions (`StopConditionMetError`, `StopConditionError`) are already implemented and exported from `aws_expect`. This phase only needs to integrate them into the existing `_poll_for_entries` loop and add a `TypeError` guard to `to_exist`.

## Dependencies Verified

| Dependency | Status | Notes |
|-----------|--------|-------|
| `StopConditionMetError` | ✅ Implemented | `exceptions.py:21`, exported in `__init__.py` |
| `StopConditionError` | ✅ Implemented | `exceptions.py:53`, exported in `__init__.py` |
| `_poll_for_entries` | ✅ Exists | `s3.py:117`, clear insertion point |
| `_fetch_body` | ✅ Exists | `s3.py:99`, returns `dict \| None` |
| Test fixtures | ✅ Established | `conftest.py` — LocalStack, `test_bucket`, `s3_resource` |

## Integration Approach

### Insertion point in `_poll_for_entries`

Current flow (lines 117-135):
```
while True:
    body = _fetch_body()          # line 128
    if body and entries match:    # line 129
        return body               # line 130
    if deadline <= 0:             # line 132
        raise timeout              # line 134
    sleep                         # line 135
```

New flow with `stop_when`:
```
while True:
    state = _fetch_body()         # no change
    if state and entries match:   # MAIN CONDITION FIRST (D-06)
        return state               # success — stop_when never checked
    # NEW: stop_when check
    if state and stop_when:       # D-02: only when body exists
        return _check_stop_condition(state, stop_when, resource_id, start, timeout)
    if deadline <= 0:             # unchanged
        raise timeout
    sleep                         # unchanged
```

### TypeError guard in `to_exist`

Location: `s3.py:85`, before the `if entries is not None:` branch.

```python
if stop_when is not None and entries is None:
    raise TypeError(
        "stop_when requires entries to be provided. "
        "Use to_exist(entries={...}, stop_when=...)"
    )
```

### State dict handling

Per D-01/D-03: `state.copy()` passed to predicate — shallow copy prevents mutation of internal state. No metadata keys injected — the resource IS its body dict.

### Predicate return convention

Per D-04/D-05:
- Return `True` → `stop_reason = "stop condition met"` (default)
- Return `str` → `stop_reason = <that string>`
- Raise non-StopConditionMetError → `StopConditionError(resource_id)` via `raise ... from`
- Raise `StopConditionMetError` → re-raise as-is

### Resource ID format

Per D-10: `f"s3://{self._bucket}/{self._key}"` — consistent with `S3WaitTimeoutError.__init__` message format.

### `StopConditionMetError` constructor compatibility

The Phase 6 constructor is:
```python
StopConditionMetError(resource_id, stop_reason, elapsed, timeout)
```

Where:
- `resource_id` = `f"s3://{bucket}/{key}"`
- `stop_reason` = predicate return value (or default string)
- `elapsed` = `time.monotonic() - start` — actual time waited before stop fired
- `timeout` = original configured timeout

## Overload Signature Design

Current overloads (lines 34-48):
```python
@overload
def to_exist(self, timeout=..., poll_interval=..., entries: dict[str, Any]=...) -> dict[str, Any]

@overload
def to_exist(self, timeout=..., poll_interval=..., entries: None=...) -> HeadObjectOutputTypeDef
```

New overload needed:
```python
@overload
def to_exist(self, timeout=..., poll_interval=..., entries: dict[str, Any]=..., *,
             stop_when: Callable[[dict[str, Any]], bool | str] | None=...) -> dict[str, Any]
```

The `stop_when` parameter is keyword-only (`*` in signature). The existing two overloads remain unchanged — `stop_when` is only meaningful with `entries`.

## Test Strategy

Tests follow the established `TestToExist` class pattern in `test_s3_exist.py`. New test class: `TestToExistStopWhen` (or extend existing class).

Test cases needed (mapped to success criteria):
1. **stop_when returns True** → `StopConditionMetError` raised with correct `stop_reason`, `elapsed`, `timeout`, `resource_id`
2. **stop_when returns str** → `StopConditionMetError` raised with that string as `stop_reason`
3. **stop_when without entries** → `TypeError` raised immediately
4. **Main-condition-wins** → entries match first, `stop_when` never called (verify via side-effect tracking)
5. **State dict shallow copy** → predicate mutation doesn't affect next iteration
6. **Predicate raises ValueError** → `StopConditionError` raised with `__cause__` set
7. **Predicate raises StopConditionMetError** → re-raised as-is
8. **stop_when=None** → existing behavior unchanged (backward compat)
9. **Object doesn't exist yet** → body is None, skip stop_when, continue polling

## Files Modified

| File | Change |
|------|--------|
| `aws_expect/s3.py` | Add `stop_when` parameter, overload, TypeError guard, `_check_stop_condition` helper, modify `_poll_for_entries` |
| `tests/test_s3_exist.py` | Add `TestToExistStopWhen` test class (or new file `test_s3_stop_when.py`) |

## Risks / Edge Cases

| Risk | Mitigation |
|------|-----------|
| `stop_when` mutates state dict | Shallow copy per D-03 |
| Body is None (NoSuchKey) | Skip stop_when per D-02 |
| Predicate crashes | Wrap in `StopConditionError` per D-07 |
| Backward compat | `stop_when=None` default, no new code paths |
| Keyword-only enforcement | `*` in signature per D-12 |
