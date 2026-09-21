# Python / Django (also Flask, FastAPI) reference for audit-injection-vulnerabilities

## Stack markers
`manage.py`, `requirements.txt`/`pyproject.toml` with `django`, `flask`, `fastapi`. Data layers: Django ORM, SQLAlchemy, `psycopg2`, `pymysql`, `pymongo`, `motor`.

## Where the relevant code lives
`**/views.py`, `**/api/**`, `**/viewsets.py`, `**/serializers.py` (sources: `request.GET`, `request.POST`, `request.data`, `request.FILES[...].name`, `kwargs` from URL patterns, FastAPI path/query params, Flask `request.args`/`request.form`/`request.json`), `**/models.py` managers with `.raw(`, `**/utils/**`, `**/tasks.py` (Celery payloads), `**/management/commands/**`, report/export modules, `templates/` loaders.

## Dangerous / interesting APIs and patterns
- SQL: `cursor.execute("..." % x)`, `cursor.execute(f"...")`, `cursor.execute("..." + x)`, `.format(` on SQL strings, `Model.objects.raw(` with interpolation, `.extra(where=[...], select=...)`, `RawSQL(` with a non-constant, `connection.cursor().executemany(f"`, `QuerySet.order_by(user_string)` (Django validates field names; `order_by` with `"-" + field` is safe unless combined with `RawSQL`), SQLAlchemy `text(f"...")`, `session.execute("..." + x)`, `engine.execute(`, `sqlalchemy.literal_column(user)`, `column(user)`.
- NoSQL: `collection.find({"$where": ...})`, `find(json.loads(user))`, `find({user_field: value})` with `user_field` from request, Django MongoEngine `__raw__=user`.
- CMD: `os.system(`, `subprocess.run|call|Popen|check_output(... shell=True`, `subprocess.*("cmd " + x)` (string with shell), `os.popen(`, `commands.getoutput(`, `pexpect.spawn(user)`, `shlex.split(user)` fed to a shell.
- PATH: `open(os.path.join(root, user))` (absolute user path escapes), `os.path.join(BASE, request.GET["f"])`, `open(user)`, `send_file(user)` / `FileResponse(open(user))`, `django.http.FileResponse`, `shutil.copy|move|rmtree(`, `os.remove(`, `pathlib.Path(root) / user` without `resolve()` + `relative_to()` check, `default_storage.open(user)`, `Path(user).read_text()`, `zipfile.extractall(` (zip slip), `tarfile.extractall(` (pre-3.12 filter).
- LDAP: `ldap.search_s(base, scope, "(uid=%s)" % user)`, `ldap3` `conn.search(search_filter=f"...")` (use `escape_filter_chars`).
- XPATH: `tree.xpath("//user[@name='%s']" % x)`, `lxml.etree.XPath(`, `ElementTree.findall(user)`; XXE: `lxml.etree.XMLParser(resolve_entities=True)` (default!), `xml.dom.minidom` on untrusted input without `defusedxml`.
- TMPL: `Template(user_string)` (django.template / jinja2), `Environment().from_string(user)`, `render_template_string(user)` (Flask), `Markup(user)`, `mark_safe(user)` (XSS side, hand to the frontend skill if server-rendered), `eval(`, `exec(`, `compile(`, `str.format(user, **ctx)` (format-string attribute access), `%` formatting with user format strings.
- SSRF: `requests.get(user)`, `httpx.get(user)`, `urllib.request.urlopen(user)`, `aiohttp.ClientSession().get(user)`, `urllib3`, `pycurl`, `wget`, `PIL.Image.open(urlopen(user))`, `feedparser.parse(user)`, `requests.get(url, allow_redirects=True)` even with a host check (redirect to internal), Django `URLField` values later fetched by a task.
- DESER: `pickle.load|loads(`, `cPickle`, `marshal.loads(`, `shelve.open(` on user paths, `yaml.load(x)` without `Loader=SafeLoader` / `yaml.unsafe_load` / `yaml.full_load` (FullLoader allowed arbitrary objects pre-5.4), `jsonpickle.decode(`, `dill.loads(`, `numpy.load(allow_pickle=True)`, `torch.load(` on uploads, Django `SESSION_SERIALIZER = PickleSerializer`, Celery `accept_content = ["pickle"]`, `pandas.read_pickle(`.

## What "good" looks like
```python
# SQL - params; sort allow-listed
cur.execute("SELECT * FROM sales WHERE branch_id = %s", [branch_id])
Sale.objects.filter(branch_id=branch_id).order_by(SORT.get(request.GET.get("sort"), "-created_on"))
session.execute(text("SELECT * FROM sales WHERE branch_id = :b"), {"b": branch_id})

# PATH - basename + confine
root = Path(settings.MEDIA_ROOT).resolve()
target = (root / Path(name).name).resolve()
if root not in target.parents: raise Http404

# CMD - list form, no shell
subprocess.run(["convert", str(target), str(out)], check=True)

# SSRF - parse and allow-list, no redirects
u = urlparse(url)
if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS: raise ValidationError
requests.get(url, allow_redirects=False, timeout=5)

# DESER - yaml.safe_load; JSON for sessions/queues; never pickle from a request.
```

## Manual trace checklist
1. List views: `ordering`, `sort`, `search` query params (DRF `OrderingFilter` is safe when `ordering_fields` is set; `ordering_fields = "__all__"` is broad but still validated) reaching `.raw()`/`.extra()`/`RawSQL`.
2. Report/export views and management commands with hand-written SQL.
3. Upload/download: `request.FILES[...].name` into storage paths; "download by name" views; `zipfile.extractall`.
4. Any view or Celery task that fetches a URL supplied in a request or model field (`webhook_url`, `logo_url`, `import_url`).
5. `yaml.load` / `pickle` in settings loaders, cache backends, session serializers, and Celery config.
6. Flask/Jinja `render_template_string` and Django `Template(` with strings that originate from the DB (email templates edited by admins count as user-controlled if admins are tenants).

## Stack-specific false positives
- `cursor.execute("... %s", [x])` - the `%s` is a DB-API placeholder, not string formatting, when a second argument is present.
- `Model.objects.raw("... WHERE id = %s", [id])` is parameterized.
- `subprocess.run([...])` list form with no `shell=True` and constant program.
- `os.path.join(BASE_DIR, "static", "x.css")` constants.
- `yaml.safe_load`, `yaml.load(x, Loader=SafeLoader)`.
- `requests.get(settings.API_URL + "/items", params={"id": id})` where the host is from settings.
- `eval` in test fixtures or Django `settings` loaders for env parsing (still note as Low if it parses env strings).

## Tooling
- `bandit -r <dir> -f json -o audit/evidence/audit-injection-vulnerabilities/bandit.json` (B102 exec, B301-B302 pickle/marshal, B307 eval, B310 urlopen, B506 yaml.load, B602-B607 subprocess/shell, B608 SQL, B324).
- `semgrep --config p/python --config p/django --config p/flask`.
- `pip-audit` for gadget-bearing packages (report under audit-dependency-vulnerabilities).

## References
Django docs "Performing raw SQL queries" and "SQL injection protection"; OWASP Python security cheat sheets; PyYAML `safe_load` docs; Python `subprocess` "Security Considerations". CWE-89, 943, 78, 22, 90, 643, 918, 502, 1336, 95, 611; ASVS 5.3.x, 5.5.x, 12.3.x, 12.6.1; OWASP A03/A08/A10:2021.
