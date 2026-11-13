# Python tooling security lock (#842)

## Scope and selection

This is a targeted **tooling** repair, not a production dependency wave or an exploit claim. The existing production `pip-audit -r requirements.txt` does not cover the development/security groups in `uv.lock`.

- `filelock 3.32.6` is in the affected ranges of [GHSA-v4x8-3wr5-3wq8](https://github.com/tox-dev/filelock/security/advisories/GHSA-v4x8-3wr5-3wq8), [GHSA-567q-5qvw-pf92](https://github.com/tox-dev/filelock/security/advisories/GHSA-567q-5qvw-pf92) and [GHSA-9vhv-jxww-xfm5](https://github.com/tox-dev/filelock/security/advisories/GHSA-9vhv-jxww-xfm5). Their first fixed release is **4.2.1**.
- Installed/PyPI metadata confirms that `virtualenv 21.7.9` requires `filelock<4,>=3.24.2` on Python >=3.10. Forcing the major upgrade without moving this parent would be invalid. `python-discovery 1.6.0` itself has no upper filelock bound; pre-commit 4.3.0 accepts virtualenv >=20.10.0.
- The first compatible parent is virtualenv **21.10.0**, but a real all-group audit rejects it: eleven reported virtualenv advisories remain, plus one msgpack advisory. PyPI advisory metadata also rejects virtualenv 21.14.9 (GHSA-4f8h-vr72-p32c, fixed 21.14.10). The smallest parent satisfying these current advisory fixes is **21.14.10**; its supported filelock range is `<5,>=3.24.2`.
- That parent requires python-discovery >=1.6.1. Select **1.6.1**, not its otherwise resolver-selected newer minor. Existing distlib 0.4.3, packaging 26.3 and platformdirs 4.11.8 already satisfy the other raised parent minima.
- `msgpack 1.2.2`, reached through security tooling's cachecontrol, is affected by [GHSA-j586-36cw-2gc2](https://github.com/advisories/GHSA-j586-36cw-2gc2). Select its first fixed patch **1.2.3**.

Exactly four locked distributions change: filelock, virtualenv, python-discovery and msgpack. No direct dependency declaration, production pin, waiver, severity threshold or scanner configuration changes. All four remain outside the production requirements export.

The official source metadata was read from the versioned PyPI JSON endpoints, e.g. `https://pypi.org/pypi/virtualenv/21.14.10/json`; the patched filelock release notes and original advisories were read separately. Package metadata/ranges are compatibility inputs, not execution proof.

## Reproduction

```sh
uv lock --upgrade-package 'filelock==4.2.1' \
  --upgrade-package 'virtualenv==21.14.10' \
  --upgrade-package 'python-discovery==1.6.1' \
  --upgrade-package 'msgpack==1.2.3'
uv lock --check
uv sync --locked --all-groups --reinstall-package streamvault
uv export --locked --no-dev --no-emit-project --no-hashes
uv export --locked --all-groups --no-emit-project --no-hashes \
  --output-file /path/to/owned-scratch/all-groups.txt
uv run pip-audit --disable-pip --no-deps --progress-spinner off \
  -r /path/to/owned-scratch/all-groups.txt
uv run pip-audit -r requirements.txt
uv run bandit -r app/ -ll -iii --exclude app/__pycache__,app/frontend
```

The no-deps audit consumes the complete pinned export; it does not suppress vulnerabilities. Its lack of requirement hashes is an explicit auditor warning, not a clean-supply-chain claim. The uv lock retains distribution hashes.

## Observed checks

- Before the repair, the committed tooling security regression fails on filelock 3.32.6; after the first compatible trial it also rejects the still-vulnerable parent. The final package-lock regression and existing packaging suite pass (16 cases).
- Actual locked Python **3.14.7** environment: version/range checks, python-discovery interpreter lookup, two concurrent real virtualenv creations sharing their own app-data cache and execution of both created interpreters pass. Actual pre-commit validates a synthetic local Python hook, installs its environment and executes it; a file written by the hook is checked. There is no project pre-commit configuration to claim as run. Fixture/cache/temporary repositories are isolated and removed afterward.
- Final all-group Linux/Python3.14 export: **115 audited distributions, zero reported known vulnerabilities**, including the fixed filelock entry. This is not an all-platform audit of all 118 lock nodes or a Windows execution result.
- The unchanged production pip-audit and exact existing CI Bandit command pass. At the tooling-only verification, Bandit's raw metrics reported 0 High / 2 Medium / 63 Low; the filtered pass is **not** an all-severity-clean claim. The separately confirmed predictable LiveStreamingService temporary-root defect is handled by the subsequent #842 lifecycle correction in the backend ledger; its fresh all-severity scan reports 0 High / 1 Medium / 63 Low. The remaining devrunner argv literal is not an established file-write defect and is not suppressed.
- With the actual four updated tooling packages installed in the native Python3.14.10 runner, the whole suite passes **1165 tests / 13 existing opt-in skips / 524 warnings / 2 subtests** (273.89s). This is a lock-change verification, not the final image or a Windows pass. Exact final-head CI, final no-push image/Hadolint checks and whole-contract acceptance remain separately required; these component/tooling results do not replace them.
