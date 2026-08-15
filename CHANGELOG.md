# Changelog

All notable changes to Loominar are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [1.0.0] - 2026-08-15

First stable release. Loominar now retrieves **complete** issue sets from
SonarQube regardless of project size, which the 0.2.x line could not do.

Earlier `v0.2.1` and `v0.3.0` tags exist in the repository, but every one of
them shipped packaging metadata that still declared `0.2.0`; the last version
actually published was `0.2.0`. This release resynchronises the tag, the
package metadata, and `loominar.__version__`.

### Fixed - the 10,000-issue ceiling

SonarQube's `/api/issues/search` rejects any request where `page * pageSize`
exceeds 10,000. Every fetch path in 0.2.x ignored that limit, so a large project
failed partway through: the streaming path fetched exactly 10,000 rows, took an
HTTP 400 on the next page, **deleted the partial file, and returned nothing** -
silently dropping the bucket from the report.

Retrieval is now layered:

- **Filter splitting.** Result sets above the inline limit are split by
  **severity**, then **type**, then creation-date windows. Severity and type
  partition the result set exactly, so buckets have no gaps and no overlap.
  (Severity splitting was documented in the code but never implemented; only
  `type`, `component`, and `date` existed.)
- **Creation-date cursor.** A bucket that is still too large is sorted by
  creation date; when the 10k window is exhausted, `createdAfter` re-anchors to
  the last issue seen and paging restarts. Issues are deduplicated by key, so
  the inclusive window boundary never yields duplicates.

Verified against a mock server that enforces the real HTTP 400: 42,000 mixed
issues and 120,000 same-severity issues both retrieved completely, with zero
duplicates and zero missing.

### Fixed - data loss and crashes

- The date splitter yielded every monthly window **and then** the unsplit filter
  again, fetching the entire result set twice, the second time as an oversized
  bucket.
- Binary date subdivision passed the wrong remaining dimensions, so oversized
  halves were never split further. `iso_midpoint` could also return a bound
  equal to its input and recurse without progress.
- Date windows covered a fixed `12 * 30` days, so **issues older than roughly a
  year were silently dropped**. Windows are now calendar months anchored on the
  project's oldest issue.
- Excel sheet names were truncated to 31 characters, so buckets sharing a long
  prefix collided and xlsxwriter raised `Duplicate worksheet name`, aborting the
  report. Names are now short, indexed, and deduplicated.
- `ExcelReport` called `self._log(...)`, which did not exist on `BaseReport` -
  an `AttributeError` whenever a bucket file was missing or cleanup ran.
- Choosing `word` or `csv` for a large project discarded every streamed bucket:
  `ReportManager` forwarded them only to the Excel writer.
- `list_components` called `/api/components/search` with a `project` parameter
  that endpoint does not accept, so it returned nothing and the component split
  silently did nothing. It now uses `/api/components/tree` with paging.
- The issue-count probe used different filters than the fetch, so the total
  driving every split decision described a different result set.
- An unreachable server exited **0** with "nothing to report", because a failed
  count probe was indistinguishable from a project with no issues. It now
  raises and exits 1.
- `_build_filename` left `ext` unbound for any format outside word/excel/csv,
  raising `UnboundLocalError`.

### Fixed - packaging

- **`loominar.api.issues` was missing from the built wheel.** The subpackage had
  no `__init__.py` and `pyproject.toml` declared no package list, so setuptools
  auto-discovery skipped it and `pip install loominar` produced an installation
  that failed at import. Packages are now listed explicitly.
- **`colorama` was a dev-only extra** but is imported at startup, so a clean
  install raised `ModuleNotFoundError`.

### Added

- Creation-date cursor pagination (`fetch_issues_cursor`) and a hard 10k guard
  on plain paging (`fetch_all_pages`).
- Constant-memory streaming: large projects are written to per-bucket CSVs under
  `<output>/.loominar_temp/` and merged into the workbook, so peak memory is
  flat regardless of project size. Temp files are removed after a successful
  merge, or kept with `--keep-temp`.
- `SONAR_URL`, `SONAR_TOKEN`, and `SONAR_PROJECT` environment variables. Passing
  `--token` exposes the token in process listings and CI logs; the environment
  is the preferred route in pipelines.
- New flags: `--inline-limit`, `--split-by`, `--keep-temp`, `--version`,
  `-q`/`--quiet`, `--debug`, `--color`/`--no-color`,
  `--timestamps`/`--no-timestamps`.
- Structured logging with aligned `[LEVEL]` tags, automatic color and timestamp
  detection, `NO_COLOR` support, and time-throttled progress reporting that
  shows throughput.
- Credential redaction: any request parameter named token/password/secret/
  authorization/login is masked before reaching a log line.
- Word reports now render the project metrics that were previously fetched and
  discarded, and truncate their detail table with a pointer to Excel.

### Changed - breaking

- **Logs go to stderr; the report path goes to stdout.** `REPORT=$(loominar ...
  --no-confirm)` now captures just the path. Anything parsing stdout for
  progress must read stderr instead.
- **CSV output schema.** Columns changed from `Severity, Type, Message, File,
  Line` to the canonical 12-column schema (adds `Status`, `Rule`, `Author`,
  `Created`, `Updated`, `Effort`, `Key`), shared with the Excel sheets so the
  merged workbook has one consistent schema.
- **Exit codes.** `0` success, `1` error, `2` cancelled, `3` missing or invalid
  input. Previously cancellation and errors both exited 1.
- **Headless mode never prompts.** With `--no-confirm`, or when stdin is not a
  TTY, a missing required value exits 3 with a message naming the flag instead
  of blocking on `input()` forever.
- **`pandas` and `openpyxl` are no longer dependencies.** Reports are written
  row-by-row through xlsxwriter and the `csv` module.
- `BaseClient._log` and `BaseReport._log` were removed. Verbosity is now global
  logger state; modules use `console.get_logger(__name__)`.
- `ExcelReport.generate` and `CsvReport.generate` accept `streamed_csvs` and
  `cleanup_temp`; `ReportManager` accepts `verbosity` and `keep_temp`.
- `monthly_windows` is superseded by `month_windows(start, end)`, and
  `iso_midpoint` returns `None` when a range cannot be split further.
- `loominar.api.__version__` was removed; the version lives only in
  `loominar.__version__`.
- Removed the unused `loominar/report/excel_stream.py` and
  `loominar/api/issues/excel_stream.py` merge helpers.

### Changed - performance

- Page size restored to 500 (from 100). The 10k cap applies to `page * pageSize`,
  so the smaller page bought no headroom and merely made every run five times
  more requests.
- Connections are pooled through a single `requests.Session` instead of a fresh
  TLS handshake per request.
- Excel severity formats are cached instead of one format object per row, which
  is what made large workbooks take minutes to write.
- Retries honour `Retry-After` and treat HTTP 408/429 as transient; other 4xx
  responses still fail immediately.
- Error messages unwrap the requests/urllib3 exception chain to a single
  readable clause instead of repeating a 400-character trace three times.

## [0.2.0] - 2025-11-12

- Initial public release: interactive and CLI modes, Word/Excel/CSV export,
  SonarQube metrics and quality gate integration, colorized console output.

[Unreleased]: https://github.com/mhmd4li/Loominar/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/mhmd4li/Loominar/compare/v0.2.0...v1.0.0
[0.2.0]: https://github.com/mhmd4li/Loominar/releases/tag/v0.2.0
