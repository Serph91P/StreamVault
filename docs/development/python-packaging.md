# Locked Python packaging

`pyproject.toml` and `uv.lock` are the canonical dependency inputs for StreamVault's Python 3.14 production line. Runtime dependencies are direct, pinned entries in `[project.dependencies]`; Streamlink is centrally pinned there at `8.4.0`. Tooling is isolated in the `dev`, `test`, `typing`, and `security` uv dependency groups.

## Local commands

```text
uv lock --check
uv sync --locked --all-groups --reinstall-package streamvault
uv run pytest tests/ -q
uv export --locked --no-dev --no-emit-project --no-hashes --output-file requirements.txt
```

`requirements.txt` is a generated, locked production compatibility export. Do not edit it manually; regenerate it with the command above whenever the lock changes.

## Version metadata

Build metadata uses setuptools-scm and Git tags without importing `app` or `Settings`. Untagged build metadata falls back to `0.0.0.dev0`. `uv sync` can retain old editable VCS metadata in a reused environment, so local and CI verification reinstall the project (`--reinstall-package streamvault`) before comparing installed metadata with a wheel built from the same Git checkout. Runtime `STREAMVAULT_VERSION`, `STREAMVAULT_BRANCH`, `STREAMVAULT_BUILD_DATE`, and `STREAMVAULT_COMMIT_SHA` variables remain owned by the existing runtime API.

## Typing boundary

The current legacy typing scope remains exactly five modules: `app/config/settings.py`, `app/core/exceptions.py`, `app/middleware/logging.py`, `app/observability.py`, and `app/routes/health.py`. New or rewritten Python modules must be typed strictly; this legacy scope must not grow before its phased migration.

## Secret-file handling

`.env` is ignored and is deliberately removed from Git tracking. Use `.env.example` placeholders only. Any credentials historically committed to repository history require operator-managed rotation; this change neither reads the local `.env` nor rewrites history or rotates credentials.
