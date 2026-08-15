from typing import Any, Dict, Iterator, Optional, Set

from loominar import console

log = console.get_logger(__name__)

# SonarQube refuses any /api/issues/search request where p * ps > 10000
# ("Can return only the first 10000 results"). This is a hard server-side
# ceiling — it cannot be paged past, only worked around with a cursor.
SONAR_RESULT_WINDOW = 10000
SONAR_MAX_PAGE_SIZE = 500

PAGE_SIZE_DEFAULT = SONAR_MAX_PAGE_SIZE

ISSUES_ENDPOINT = "/api/issues/search"


def _describe(filters: Dict[str, Any]) -> str:
    """
    Compact, human-readable name for a filter bucket.

    Log lines carry this instead of the raw params dict, which is mostly
    boilerplate (componentKeys, statuses, ps, p) repeated on every line.
    """
    if not filters:
        return "all issues"
    parts = []
    for key, label in (("severities", ""), ("types", ""), ("componentKeys", "in ")):
        value = filters.get(key)
        if value:
            parts.append(f"{label}{value}")
    after, before = filters.get("createdAfter"), filters.get("createdBefore")
    if after or before:
        parts.append(f"{str(after or '')[:19]}..{str(before or '')[:19]}")
    return " ".join(parts) if parts else "all issues"


def max_reachable_pages(page_size: int) -> int:
    """How many pages of `page_size` fit inside Sonar's 10k result window."""
    page_size = max(1, min(page_size, SONAR_MAX_PAGE_SIZE))
    return max(1, SONAR_RESULT_WINDOW // page_size)


class ProbeError(RuntimeError):
    """The count query failed, so the size of the result set is unknown."""


def probe_total(client, endpoint: str, params: Dict[str, Any], required: bool = False) -> int:
    """
    Cheapest possible count query.

    A failed probe is not the same as a project with no issues: reporting 0 for
    an unreachable server made the whole run exit 0 with "nothing to report".
    `required=True` raises instead, so the caller can fail the pipeline.
    """
    try:
        data = client.get(endpoint, {**params, "ps": 1, "p": 1})
    except Exception as exc:
        if required:
            raise ProbeError(str(exc)) from exc
        log.warning("Count probe failed for %s; skipping this bucket: %s", _describe(params), exc)
        return 0
    total = (data.get("paging") or {}).get("total", 0)
    log.debug("Count probe %s -> %s issues", _describe(params), f"{total:,}")
    return total


def fetch_all_pages(
    client,
    endpoint: str,
    base_params: Dict[str, Any],
    page_size: int = PAGE_SIZE_DEFAULT,
    strict: bool = False,
) -> Iterator[Dict[str, Any]]:
    """
    Page through `endpoint` and yield issues.

    Stops at Sonar's 10k result window rather than walking into a guaranteed
    HTTP 400. Use `fetch_issues_cursor` when the result set may exceed it.

    A failing page is logged and ends the iteration instead of propagating, so
    the caller keeps everything fetched so far. Pass `strict=True` to re-raise.
    """
    page_size = max(1, min(page_size, SONAR_MAX_PAGE_SIZE))
    params = dict(base_params)
    params["ps"] = page_size
    params["p"] = 1

    try:
        first = client.get(endpoint, params)
    except Exception as exc:
        log.error("Could not fetch page 1 of %s (%s): %s", endpoint, _describe(base_params), exc)
        if strict:
            raise
        return

    if not first:
        return

    for issue in first.get("issues") or []:
        yield issue

    paging = first.get("paging") or {}
    total_pages = paging.get("pages") or 1
    reachable = max_reachable_pages(page_size)

    if total_pages > reachable:
        log.warning(
            "%s results exceed Sonar's %d-result window; plain paging can only reach the "
            "first %d. Use the creation-date cursor to retrieve the rest.",
            paging.get("total", "?"), SONAR_RESULT_WINDOW, reachable * page_size,
        )
        total_pages = reachable

    log.debug("Paging %s: %d page(s) of %d", _describe(base_params), total_pages, page_size)

    for p in range(2, total_pages + 1):
        params["p"] = p
        try:
            data = client.get(endpoint, params)
        except Exception as exc:
            log.error(
                "Stopped at page %d/%d of %s: %s. Keeping the %d pages already fetched.",
                p, total_pages, _describe(base_params), exc, p - 1,
            )
            if strict:
                raise
            return
        batch = (data or {}).get("issues") or []
        if not batch:
            return
        for issue in batch:
            yield issue


def fetch_issues_cursor(
    client,
    base_params: Dict[str, Any],
    page_size: int = PAGE_SIZE_DEFAULT,
    seen: Optional[Set[str]] = None,
) -> Iterator[Dict[str, Any]]:
    """
    Yield every issue matching `base_params`, regardless of how many there are.

    Sonar's 10k window is per *query*, not per project, so the way past it is to
    re-anchor the query. Issues are sorted by creation date ascending; once the
    window is exhausted, `createdAfter` is moved to the last creation date seen
    and paging restarts at page 1. `createdAfter` is inclusive, so the boundary
    issues repeat — `seen` drops them.

    Pass a shared `seen` set across buckets to deduplicate the whole run.
    """
    page_size = max(1, min(page_size, SONAR_MAX_PAGE_SIZE))
    if seen is None:
        seen = set()

    params = dict(base_params)
    params["ps"] = page_size
    params["s"] = "CREATION_DATE"
    params["asc"] = "true"

    reachable = max_reachable_pages(page_size)
    cursor = base_params.get("createdAfter")
    windows = 0

    while True:
        if cursor:
            params["createdAfter"] = cursor

        windows += 1
        page = 1
        last_creation = None
        yielded_this_window = 0
        window_total = None
        exhausted_window = False

        while page <= reachable:
            params["p"] = page
            try:
                data = client.get(ISSUES_ENDPOINT, params)
            except Exception as exc:
                log.error(
                    "Cursor fetch stopped at page %d of %s (createdAfter=%s): %s",
                    page, _describe(base_params), cursor or "start", exc,
                )
                return

            batch = (data or {}).get("issues") or []
            if window_total is None:
                window_total = ((data or {}).get("paging") or {}).get("total", 0)

            if not batch:
                return

            for issue in batch:
                key = issue.get("key")
                created = issue.get("creationDate")
                if created:
                    last_creation = created
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                yielded_this_window += 1
                yield issue

            # Every page of this window has been read — the query is complete.
            if page * page_size >= (window_total or 0):
                return

            page += 1
        else:
            exhausted_window = True

        if not exhausted_window or not last_creation:
            return

        if last_creation == cursor:
            # A single timestamp holds more issues than the whole window. Paging
            # cannot advance; narrow the query (severity/type) to reach the rest.
            log.warning(
                "More than %d issues share creation date %s, so the cursor cannot advance.\n"
                "Issues in %s beyond that point will be missing from this report.\n"
                "Re-run with --split-by severity,type,component,date to narrow the query.",
                reachable * page_size, cursor, _describe(base_params),
            )
            return

        if yielded_this_window == 0:
            return

        log.debug(
            "Result window %d exhausted at %d issues; re-anchoring createdAfter=%s",
            windows, windows * reachable * page_size, last_creation,
        )
        cursor = last_creation


# Paging helpers for /api/issues/search.
# fetch_all_pages     - plain paging, capped at Sonar's 10k window.
# fetch_issues_cursor - creation-date cursor, unbounded result sets.
