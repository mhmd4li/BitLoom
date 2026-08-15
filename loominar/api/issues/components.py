from typing import List

from loominar import console

log = console.get_logger(__name__)

# /api/components/tree walks the component tree of a single project, which is
# what we actually want. /api/components/search takes `q` + `qualifiers` and has
# no `project` parameter — calling it with `project=` returns nothing useful.
_TREE_ENDPOINT = "/api/components/tree"
_SEARCH_ENDPOINT = "/api/components/search"

# Directories first: far fewer buckets than files, and a DIR bucket already
# covers its files. Only fall back to FIL when a project has no directories.
_QUALIFIER_CANDIDATES = ["DIR", "FIL"]

_PAGE_SIZE = 500
# Sonar applies the same 10k result window here.
_MAX_PAGES = 20


def _fetch_tree(client, project_key: str, qualifiers: str) -> List[str]:
    keys: List[str] = []
    page = 1
    while page <= _MAX_PAGES:
        resp = client.get(
            _TREE_ENDPOINT,
            {
                "component": project_key,
                "qualifiers": qualifiers,
                "strategy": "all",
                "ps": _PAGE_SIZE,
                "p": page,
            },
        )
        comps = (resp or {}).get("components") or []
        if not comps:
            break
        keys.extend(c["key"] for c in comps if c.get("key"))

        paging = (resp or {}).get("paging") or {}
        total = paging.get("total", len(keys))
        if page * _PAGE_SIZE >= total:
            break
        page += 1
    return keys


def list_components(client, project_key: str) -> List[str]:
    """
    Component keys under `project_key`, used to split oversized issue queries.

    Returns directory keys when the project has directories, otherwise file
    keys. Returns an empty list on any error — callers treat that as "this
    split dimension is unavailable" and move on to the next one.
    """
    for qualifier in _QUALIFIER_CANDIDATES:
        try:
            keys = _fetch_tree(client, project_key, qualifier)
        except Exception as exc:
            log.debug("Component listing by %s failed: %s", qualifier, exc)
            continue
        if keys:
            log.debug("Found %d %s components in '%s' to split by", len(keys), qualifier, project_key)
            return keys

    # Last resort for Sonar versions that reject /api/components/tree.
    try:
        resp = client.get(_SEARCH_ENDPOINT, {"q": project_key, "qualifiers": "TRK", "ps": _PAGE_SIZE})
        comps = (resp or {}).get("components") or []
        keys = [c["key"] for c in comps if c.get("key")]
        log.debug("Component search fallback returned %d keys", len(keys))
        return keys
    except Exception as exc:
        log.warning(
            "Could not list components of '%s' (%s); skipping the component split dimension.",
            project_key, exc,
        )
        return []


# Return component keys for a project. Returns empty list on error.
