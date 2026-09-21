# Python / Django (Flask, FastAPI) reference for audit-licensing-and-compliance

Where licence information lives for pip dependencies, what resolves offline, which
packages carry copyleft terms (often through compiled extensions), and how notices are
shipped for a Python service.

## Stack markers
`requirements*.txt`, `pyproject.toml` (`[project] dependencies`, Poetry `[tool.poetry.dependencies]`),
`Pipfile` / `Pipfile.lock`, `poetry.lock`, `setup.py` / `setup.cfg`, a virtualenv in the repo
(`.venv/`, `venv/`) whose `site-packages/*.dist-info/METADATA` is the offline licence source.

## Where the relevant code lives
- Direct deps: requirements files (often split `base.txt` / `production.txt` / `dev.txt` - only production is shipped), `pyproject.toml`.
- Resolved graph: `poetry.lock` / `Pipfile.lock` (versions only, no licences), `pip freeze` output.
- Licence metadata: `METADATA` lines `License:` (free text, often `UNKNOWN`), `License-Expression:` (PEP 639, SPDX), and `Classifier: License :: OSI Approved :: MIT License`. The script reads all three; the classifier is usually the reliable one.
- Licence text: `*.dist-info/LICENSE*` or `licenses/` folder (PEP 639 `License-File:`).
- Compiled extensions (`*.so` / `*.pyd`) link system libraries whose licences apply: `mysqlclient` (GPL-2.0 because of libmysqlclient), `pyqt5`/`pyqt6` (GPL or commercial), `python-ldap` (PSF; links OpenLDAP), `pycurl` (LGPL/MIT dual), `psycopg2` (LGPL - fine), `lxml` (BSD; libxml2 MIT).
- Shipping the notices: `THIRD-PARTY-NOTICES.md` in the repo and in the image; Django `/about/` view or admin index; a `NOTICE` route for APIs.

## Dangerous / interesting APIs and patterns
- Django ecosystem packages with non-permissive terms: **django-grappelli** (BSD), **django-jet** (AGPL), **django-suit** (commercial for non-personal), **weasyprint** (BSD; bundles pango/cairo LGPL - fine), **xhtml2pdf** (Apache; uses reportlab BSD), **reportlab** (BSD; the *PLUS* edition is commercial), **pdfkit** (MIT wrapper around wkhtmltopdf LGPL), **camelot**/**ghostscript** (Ghostscript is AGPL), **paramiko** (LGPL - fine), **ansible** (GPL-3.0 - as a library it is a strong-copyleft dependency), **pymssql** (LGPL), **mysqlclient** (GPL), **qrcode** (BSD), **Pillow** (HPND/MIT-like, fine).
- `License: UNKNOWN` with no classifier - unknown until the repo is checked.
- `-e git+https://...` and `https://.../pkg.tar.gz` requirements - no PyPI metadata.
- Vendored code under `vendor/` or `third_party/` copied from GPL projects (grep pass).
- Wheels that bundle binaries (`manylinux` wheels with `.libs/`) - the bundled library's licence applies.

## What "good" looks like
```bash
# CI gate
pip install pip-licenses
pip-licenses --from=mixed --format=json --with-urls --with-license-file --no-license-path \
  --ignore-packages pip setuptools wheel > audit/evidence/audit-licensing-and-compliance/pip-licenses.json
pip-licenses --fail-on "GNU General Public License v3 (GPLv3);GNU Affero General Public License v3 (AGPLv3);GNU General Public License v2 (GPLv2)" \
  --allow-only "MIT License;BSD License;Apache Software License;ISC License (ISCL);Python Software Foundation License;Mozilla Public License 2.0 (MPL 2.0);GNU Library or Lesser General Public License (LGPL)"
pip-licenses --format=markdown --with-authors > THIRD-PARTY-NOTICES.md
```
Install production requirements only (`requirements/production.txt`) before running it so dev tools do not pollute the list.

## Manual trace checklist
1. Every `unknown` package: check the classifier on PyPI or the repo's LICENSE; `UNKNOWN` in `License:` is normal.
2. Database driver: `mysqlclient` (GPL) vs `PyMySQL` (MIT) / `mysql-connector-python` (GPL with FOSS exception); `psycopg2` LGPL is fine.
3. PDF/report stack: wkhtmltopdf/weasyprint/Ghostscript - which binary is actually installed in the Docker image (`apt-get install ghostscript` = AGPL tool; running it is fine, embedding it in a shipped product is not).
4. VCS/URL requirements: upstream licence and whether the fork changed anything.
5. If the service is shipped on-prem (Docker image to customers), re-run with `--model proprietary`.
6. Where notices are exposed (About page, `/licenses`, docs).

## Stack-specific false positives
- `Django`, `djangorestframework`, `celery`, `gunicorn`, `uvicorn`, `requests` - BSD/MIT; `unknown` only when no venv is present.
- Dev-only requirements (pytest, black, mypy, coverage) - not shipped.
- `psycopg2`/`psycopg2-binary` LGPL - used unmodified via pip, approved as `review`.
- GPL command-line tools installed in the image but never linked into the app (e.g. `ghostscript` invoked via subprocess) - not distribution unless the image is shipped.

## Tooling
- `pip-licenses` (formats: json, markdown, csv; `--fail-on`, `--allow-only`, `--with-license-file`).
- `pip-audit` for CVEs alongside; `cyclonedx-py environment` for an SBOM with licences.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py --patterns scripts/patterns/python-django.json` - vendored GPL headers, copyleft `license =` in pyproject/setup, VCS requirements, known-copyleft packages.

## References
PEP 639 (licence metadata), PyPI classifiers list, pip-licenses README, Django "third-party packages" guidance;
SPDX licence list; ASVS 4.0.3 V14.2; CWE-1104.
