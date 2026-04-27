# Changelog

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
