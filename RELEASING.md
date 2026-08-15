# Releasing Loominar

Manual release process. Everything runs from a clean checkout of the branch
being released.

## 1. Bump the version

The version appears in exactly two places, and they must match:

| File | Line |
| ---- | ---- |
| `pyproject.toml` | `version = "X.Y.Z"` |
| `loominar/__init__.py` | `__version__ = "X.Y.Z"` |

Check them:

```bash
python -c "import loominar, tomllib; print(loominar.__version__, tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
```

> Versions drifted from tags in the 0.2.x line: `v0.2.1` and `v0.3.0` were both
> tagged while the metadata still said `0.2.0`, so PyPI never received them.
> Confirm the two values match **before** tagging.

## 2. Update the changelog

Move the `[Unreleased]` entries into a new `## [X.Y.Z] - YYYY-MM-DD` section in
`CHANGELOG.md`, and update the link definitions at the bottom of the file.

## 3. Build

```bash
python -m pip install --upgrade build twine
rm -rf dist build *.egg-info
python -m build
```

This produces `dist/loominar-X.Y.Z-py3-none-any.whl` and
`dist/loominar-X.Y.Z.tar.gz`.

## 4. Verify the artifacts

Metadata check:

```bash
python -m twine check dist/*
```

**Confirm every subpackage is in the wheel.** `loominar.api.issues` was missing
from the 0.2.x wheels, which made a fresh install fail at import:

```bash
python -c "import zipfile,glob; print('\n'.join(sorted(n for n in zipfile.ZipFile(glob.glob('dist/*.whl')[0]).namelist() if n.endswith('.py'))))"
```

Expect `loominar/`, `loominar/api/`, `loominar/api/issues/`, and
`loominar/report/` modules. Any new subpackage must first be added to
`[tool.setuptools] packages` in `pyproject.toml`.

Install the built wheel into a throwaway environment and smoke-test it:

```bash
python -m venv /tmp/loominar-check
/tmp/loominar-check/bin/pip install dist/loominar-*.whl   # Windows: Scripts\pip.exe
/tmp/loominar-check/bin/loominar --version
/tmp/loominar-check/bin/loominar --help
```

The install must succeed with no extra flags — that catches a runtime
dependency accidentally left in the `dev` extra, which is how `colorama` broke
0.2.0.

## 5. Publish

Upload to TestPyPI first if the packaging metadata changed:

```bash
python -m twine upload --repository testpypi dist/*
```

Then the real index:

```bash
python -m twine upload dist/*
```

Credentials come from `~/.pypirc` or the `TWINE_USERNAME` / `TWINE_PASSWORD`
environment variables (use `__token__` as the username with a PyPI API token).
Never commit a token.

## 6. Tag and push

```bash
git commit -am "release: vX.Y.Z"
git tag -a vX.Y.Z -m "Loominar X.Y.Z"
git push origin <branch> --follow-tags
```

Then draft the GitHub release, pasting that version's `CHANGELOG.md` section as
the release notes.

## Versioning policy

Loominar follows [Semantic Versioning](https://semver.org/):

- **MAJOR** — breaking changes to the CLI contract (flags, exit codes, what is
  written to stdout) or to the output schema of a report format.
- **MINOR** — new features and formats, backwards compatible.
- **PATCH** — bug fixes only.

The CLI surface is a public API: flag names, the four exit codes (`0` success,
`1` error, `2` cancelled, `3` bad input), the stderr/stdout split, and the CSV
column schema are all covered by this policy.
