# Changelog

All notable changes to `dynamic-config-nacos` will be documented in this file.

Author: FrankTang (<franktz2003@gmail.com>)

License: MIT

## [0.1.2] - 2026-03-19

### Added

- Added `sdk_log_path` and `sdk_log_level` to `NacosSettings` so callers can
  route `nacos-python-sdk` logs to a dedicated directory or explicit log file.
- Added `NACOS_SDK_LOG_PATH` and `NACOS_SDK_LOG_LEVEL` environment-variable
  support in `load_from_env()`.

### Improved

- Kept SDK log routing isolated from the application's root `logging`
  configuration for `sdk_v2` and `sdk_v3` backends.
- Supported explicit file targets such as `logs/nacos.log` in addition to log
  directories for SDK-backed Nacos clients.
- Documented the separate SDK logging setup in the English and Simplified
  Chinese README and usage guide.

## [0.1.1] - 2026-03-15

### Fixed

- Fixed `NACOS_BACKEND=auto` so it no longer tries the legacy `nacos` import
  path first when only the current `nacos-sdk-python` 3.x `v2.nacos` path is
  available.
- Added a dedicated `sdk_v3` implementation for the current
  `nacos-sdk-python` 3.x async config service API.
- Kept `sdk_v2` as a legacy path for environments that still provide the old
  `nacos` package import.

### Improved

- Filtered unavailable SDK backends before trying the auto-selected backend
  order.
- Added clearer watcher startup logs for `http`, `sdk_v2`, and `sdk_v3`
  backends.
- Updated the applied-update log so it reports the active backend instead of
  only the configured `auto` value.
- Expanded test coverage for backend selection, SDK compatibility, and watcher
  logging.
- Updated English and Simplified Chinese docs with backend-selection and
  watcher-behavior details.

## [0.1.0] - 2026-03-15

### Added

- Initial public release of `dynamic-config-nacos`.
