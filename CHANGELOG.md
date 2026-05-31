# Changelog

## [3.0.0](https://github.com/PhishStick-hub/aws-expect/compare/v2.2.0...v3.0.0) (2026-05-31)


### ⚠ BREAKING CHANGES

* **dynamodb:** DynamoDBTableExpectation now accepts Table resource instead of (resource, table_name)

### Code Refactoring

* **dynamodb:** separate item and table responsibilities ([3b1fed6](https://github.com/PhishStick-hub/aws-expect/commit/3b1fed61dfbec8719821ce389514c4df00d91297))

## [2.2.0](https://github.com/PhishStick-hub/aws-expect/compare/v2.1.0...v2.2.0) (2026-05-28)


### Features

* **dynamodb:** add datetime validation and table emptiness waiters ([3e3a6c8](https://github.com/PhishStick-hub/aws-expect/commit/3e3a6c8adf5d24b0732261de28c551807f6f1c66))
* **dynamodb:** add to_be_empty and to_be_not_empty to DynamoDBTableExpectation ([aa6eccf](https://github.com/PhishStick-hub/aws-expect/commit/aa6eccfcfa4b2a3f0bd3d27225dc1d195135ffae))
* **dynamodb:** add to_have_datetime_close_to for timestamp field validation ([2d8dd6d](https://github.com/PhishStick-hub/aws-expect/commit/2d8dd6dd94a3785cab745ab90ca2c5af680499ed))

## [2.1.0](https://github.com/PhishStick-hub/aws-expect/compare/v2.0.0...v2.1.0) (2026-05-27)


### Features

* **s3:** add to_not_appear method for guarding against object creation ([7ae4881](https://github.com/PhishStick-hub/aws-expect/commit/7ae4881d4074b9193a1939e1553732904a90a840))


### Documentation

* **s3:** clarify shallow vs deep matching and trim verbose docstrings ([5e176c5](https://github.com/PhishStick-hub/aws-expect/commit/5e176c522d66be1ad3a00ffc4cb39d8740d258f6))

## [2.0.0](https://github.com/PhishStick-hub/aws-expect/compare/v1.4.0...v2.0.0) (2026-05-18)


### ⚠ BREAKING CHANGES

* **parallel:** simplify tuple format in expect_all/expect_any

### Features

* **parallel:** simplify tuple format in expect_all/expect_any ([cb3a4f0](https://github.com/PhishStick-hub/aws-expect/commit/cb3a4f02cbcd25d8466454c04c6ca630bf1fbc6d))

## [1.4.0](https://github.com/PhishStick-hub/aws-expect/compare/v1.3.0...v1.4.0) (2026-05-10)


### Features

* **parallel:** support (fn, args, kwargs) tuples in expect_all and expect_any ([78f8c25](https://github.com/PhishStick-hub/aws-expect/commit/78f8c25df9b44aac0b7e8ebd24d69aa42ed1ec10))


### Documentation

* **10:** capture phase context for Core Dispatch Implementation ([d45a4c2](https://github.com/PhishStick-hub/aws-expect/commit/d45a4c2a3b8dc738b68bb2daf72a387467a25ff7))
* **10:** research and plan phase 10 — core dispatch implementation ([25daec3](https://github.com/PhishStick-hub/aws-expect/commit/25daec30f8f6edadbd2c915251d7e62ba5993e9f))
* **11:** capture phase context ([c1c52f9](https://github.com/PhishStick-hub/aws-expect/commit/c1c52f95a13d304fbc775c2d106e3ced85453c9c))
* **11:** create phase plan — type polish, edge testing, docs ([0cd190a](https://github.com/PhishStick-hub/aws-expect/commit/0cd190a54731f6e71b0903aa93628737de675cde))
* create milestone v1.4.0 roadmap (2 phases) ([7420471](https://github.com/PhishStick-hub/aws-expect/commit/74204710eb1bb61311b088daaa9c9fff5fd97817))
* define milestone v1.4.0 requirements ([46053bc](https://github.com/PhishStick-hub/aws-expect/commit/46053bc10d24dd121d9be8901a389a17e2d9724f))
* **readme:** add tuple-form examples for expect_all and expect_any ([6b954d0](https://github.com/PhishStick-hub/aws-expect/commit/6b954d0d6343d7b053e12d082c29e6a583856e91))
* **research:** synthesize project research for v1.4.0 lambda-args ([9f9ebed](https://github.com/PhishStick-hub/aws-expect/commit/9f9ebed430ccac5941a4705b17d6e05b3f73db24))
* start milestone v1.4.0 Lambda Args for expect_all / expect_any ([ac72b5e](https://github.com/PhishStick-hub/aws-expect/commit/ac72b5ed961e06dcbac486989a84aa5be4e75e5f))
* **state:** record phase 10 context session ([24b7550](https://github.com/PhishStick-hub/aws-expect/commit/24b7550ca5325f32cc88757603724f6017140ca4))
* **state:** record phase 11 context session ([f75eb09](https://github.com/PhishStick-hub/aws-expect/commit/f75eb0936dfd44d6e065315f4a5a24109e699e52))

## [1.3.0](https://github.com/PhishStick-hub/aws-expect/compare/v1.2.0...v1.3.0) (2026-05-10)


### Features

* **08-02:** add stop_when parameter to to_exist with resource ID helper, TypeError guard, and polling loop integration ([2e23bac](https://github.com/PhishStick-hub/aws-expect/commit/2e23bacfc9fb99cc26e39be9f93e8e1bc9a58640))
* **08-02:** add stop_when parameter to to_find_item with per-item evaluation and scan abort ([cca20e6](https://github.com/PhishStick-hub/aws-expect/commit/cca20e69454d571f17fc96f9ec29b9f33d6aa4e3))
* **09-01:** add expected/actual class-level defaults to WaitTimeoutError ([e03070e](https://github.com/PhishStick-hub/aws-expect/commit/e03070e50db79bc85e2df639ac69c9f3f31acc90))
* **09-01:** implement _format_timeout_error with Expected:/Actual: sections ([badbc4c](https://github.com/PhishStick-hub/aws-expect/commit/badbc4cd15ed1c7121c152996771c00255a60b5b))
* **09-01:** implement _truncate_value with truncation guards ([ff07b09](https://github.com/PhishStick-hub/aws-expect/commit/ff07b0964a56395fd8d848f5c8b3f5c753938d3c))
* **09-02:** rename call site parameters in dynamodb.py and sqs.py ([e7f9ad4](https://github.com/PhishStick-hub/aws-expect/commit/e7f9ad4a4db23942e742b7427416a1efc793d5e8))
* **09-02:** wire all 8 WaitTimeoutError subclasses to _format_timeout_error ([9bc02eb](https://github.com/PhishStick-hub/aws-expect/commit/9bc02eb99d9703331f940e8fa7cff5491eaf819d))


### Documentation

* **06:** capture phase context ([699e4ca](https://github.com/PhishStick-hub/aws-expect/commit/699e4ca4d31962d7dab09308b19993515fb24133))
* **06:** research and plan for Exception Foundation phase ([5dc0ffe](https://github.com/PhishStick-hub/aws-expect/commit/5dc0ffebc1df0aaec91e04e4accc0f9b3ecb7542))
* **07:** capture phase 7 context ([cd1ade9](https://github.com/PhishStick-hub/aws-expect/commit/cd1ade9e0cdfb5648afb5e13dc1a5cdd13bfddd3))
* **07:** create phase plan for S3 Smart Polling ([f4ab458](https://github.com/PhishStick-hub/aws-expect/commit/f4ab458fca3101c9bb94298e2df094fc6268551b))
* **08-01:** complete extract shared stop-condition plan ([cdaade8](https://github.com/PhishStick-hub/aws-expect/commit/cdaade85ff1b3cfe5670bdda3a6ca05fe16a33e8))
* **08-02:** complete add stop_when to DynamoDB to_exist and to_find_item plan ([786ae46](https://github.com/PhishStick-hub/aws-expect/commit/786ae4646032fbdf822f32fd38169c335e3c35cc))
* **08-03:** complete DynamoDB stop_when integration tests plan ([e69e8f6](https://github.com/PhishStick-hub/aws-expect/commit/e69e8f6a8a74527e9e7b50c5c0cd32c990fac2c5))
* **09-01:** complete shared truncation and formatting helpers plan ([bf8787e](https://github.com/PhishStick-hub/aws-expect/commit/bf8787ee7df0ad59397a44f206a011c188649004))
* **09-02:** complete richer-timeout-errors-wiring plan ([80ac3f6](https://github.com/PhishStick-hub/aws-expect/commit/80ac3f6f1f8a086aaa0ea653a52aaae931691af8))
* **09:** capture phase context ([d8e35ad](https://github.com/PhishStick-hub/aws-expect/commit/d8e35ad7cf555ba8df4221ddadb25ccf7fcbe55e))
* **09:** create phase plan for richer-timeout-errors ([33c83b2](https://github.com/PhishStick-hub/aws-expect/commit/33c83b2264cc03cdcf2f6b2c0f6cdc94715a40f7))
* complete project research — stop_when, richer errors, architecture, pitfalls ([6b6b1d0](https://github.com/PhishStick-hub/aws-expect/commit/6b6b1d00fbe08c37e6d5f235ee06355004c35c79))
* **phase-09:** update tracking after wave 1 ([53792c0](https://github.com/PhishStick-hub/aws-expect/commit/53792c0969ec06b1bfc97b02cc9f54b25c3f8772))
* **phase-09:** update tracking after wave 2 ([e09043d](https://github.com/PhishStick-hub/aws-expect/commit/e09043d13ba7eed1b9d336216020c6dd997a3ce1))
* **readme:** add stop_when, content matching, and exception docs for v1.3.0 ([05df821](https://github.com/PhishStick-hub/aws-expect/commit/05df8210b64c4e0ff638012863e715cee34c9e7f))
* **state:** record phase 09 context session ([356b123](https://github.com/PhishStick-hub/aws-expect/commit/356b1236766fc5bee12b04e323ab94284ca0318c))
* **state:** record phase 6 context session ([9119f07](https://github.com/PhishStick-hub/aws-expect/commit/9119f07e33cc490203297acaf9f8a77edfbd97bc))
* **state:** record phase 7 context session ([ff647bb](https://github.com/PhishStick-hub/aws-expect/commit/ff647bb64b05f2c8a380e28678720f9680880a91))

## [1.2.0](https://github.com/PhishStick-hub/aws-expect/compare/v1.1.0...v1.2.0) (2026-04-29)


### Features

* **dx:** add parallel execution support with expect_all and expect_any ([a7be4c4](https://github.com/PhishStick-hub/aws-expect/commit/a7be4c45b394d4049f80d96100bf6b581c495d81))

## [1.1.0](https://github.com/PhishStick-hub/aws-expect/compare/v1.0.0...v1.1.0) (2026-04-27)


### Features

* add richer assertions for S3 content, DynamoDB scan, and Lambda response ([#21](https://github.com/PhishStick-hub/aws-expect/issues/21)) ([0cd7d1a](https://github.com/PhishStick-hub/aws-expect/commit/0cd7d1aa6b9780f546034502c4f2bfff554e2bd4))

## [1.0.0](https://github.com/PhishStick-hub/aws-expect/compare/v0.6.1...v1.0.0) (2026-04-14)


### ⚠ BREAKING CHANGES

* **core:** DynamoDBNonNumericFieldError now inherits Exception directly instead of WaitTimeoutError. Code catching WaitTimeoutError will no longer catch non-numeric field errors — which was the incorrect behavior documented in the class docstring. Aligns with LambdaResponseMismatchError semantics.

### Features

* **core:** extract shared utils and fix DynamoDBNonNumericFieldError hierarchy ([#18](https://github.com/PhishStick-hub/aws-expect/issues/18)) ([49f411a](https://github.com/PhishStick-hub/aws-expect/commit/49f411ac71620179f27b924d6f52b6116d2340a8))

## [0.6.1](https://github.com/PhishStick-hub/aws-expect/compare/v0.6.0...v0.6.1) (2026-04-12)


### Documentation

* **contributing:** rewrite for release-please + release/** testpypi flow ([a6bd07c](https://github.com/PhishStick-hub/aws-expect/commit/a6bd07c318e83fcefb7be449e2d8527d2f6a1c09))
