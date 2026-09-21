# Python / Django (also Flask/Jinja2, FastAPI templates) reference for audit-frontend-xss-and-dom-safety

XSS is mostly a client topic; this file covers the Python server side: Django
and Jinja2 templates, `mark_safe`/`Markup`, HTML-returning views, and the
server-side sanitization a frontend bypass may rely on.

## Stack markers
`manage.py`, `requirements.txt`/`pyproject.toml` with `django`, `flask`, `jinja2`, `fastapi` + `jinja2`; `templates/**`, `static/**`.

## Where the relevant code lives
`templates/**/*.html`, `**/templatetags/**` (custom filters returning `mark_safe`), `**/views.py` (`HttpResponse("<html>" + x)`, `render_template_string`), `**/forms.py` widgets, `**/admin.py` (`format_html`/`mark_safe` in list_display), `static/js/**` (raw DOM code), `**/utils/html*.py`, `bleach`/`nh3`/`html-sanitizer` usage (server-side sanitizers), DRF renderers producing HTML, email builders.

## Dangerous / interesting APIs and patterns
- Bypasses (BYPASS/SSR): Django `{{ x|safe }}`, `{% autoescape off %}`, `mark_safe(x)`, `SafeString`, `format_html(x)` with the *template* from input (args are escaped, the format string is not), `format_html_join` misuse, `escape` applied then `mark_safe` on concatenation, `|safeseq`, `{% include x %}` with user path; Jinja2 `{{ x|safe }}`, `Markup(x)`, `Markup(x) % ...` (safe), `Environment(autoescape=False)` (Jinja2 default!), `render_template_string(user)` (SSTI - injection skill), `{% autoescape false %}`; Flask `Markup`; `django-ckeditor`/`django-tinymce` fields rendered with `|safe` without `bleach` on save.
- HTML in code: `HttpResponse("<h1>" + x)`, `HttpResponse(f"...{x}...")`, `render_to_string` with `mark_safe` context, `JsonResponse` with `safe=False` (not XSS - name collision, ignore), `return f"<html>..."` in Flask views.
- Script context: `<script>var d = {{ data|safe }};</script>` - use `json_script` filter (`{{ data|json_script:"id" }}`) or `escapejs`; `{{ x|escapejs }}` inside JS strings only.
- URLs: `<a href="{{ user_url }}">` - autoescape encodes but does not check scheme (`javascript:`); `HttpResponseRedirect(request.GET.get("next"))` without `url_has_allowed_host_and_scheme` (open redirect, CWE-601); Django `URLField` accepts `javascript:`? No (validates scheme) but `CharField` does.
- Static JS (`static/js/**`): `innerHTML =`, `document.write(`, `$(...).html(`, `eval(`, `location.href = `, jQuery `$(location.hash)` selector injection.
- SRI/INLINE: base templates with `<script src="https://cdn...">` without `integrity`; inline `<script>` blocks with `{{ }}` values; `django-csp` `CSP_SCRIPT_SRC` with `'unsafe-inline'` (owned by headers skill).
- Sanitizers: `bleach.clean(x, tags=..., attributes=...)` (deprecated but common), `nh3.clean(x)`, `html_sanitizer`, `lxml.html.clean.Cleaner`. A frontend "the API sanitizes" claim is justified only if one runs on the **write** path (serializer `validate_<field>`, model `save`, form `clean_<field>`).

## What "good" looks like
```django
{# Django autoescapes #}
<p>{{ comment.body }}</p>
{# Justified |safe: article.safe_html is produced by nh3.clean in HelpArticle.save() #}
<div>{{ article.safe_html|safe }}</div>
{{ page_data|json_script:"page-data" }}
<script>const d = JSON.parse(document.getElementById('page-data').textContent);</script>
<script src="https://cdn.example.com/lib.js" integrity="sha384-..." crossorigin="anonymous"></script>
```
```python
import nh3
class HelpArticle(models.Model):
    def save(self, *a, **k):
        self.safe_html = nh3.clean(self.html, tags={"p","b","i","a","ul","li","table","tr","td"}, attributes={"a": {"href"}})
        super().save(*a, **k)
# redirects
from django.utils.http import url_has_allowed_host_and_scheme
if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}): return redirect(nxt)
```

## Manual trace checklist
1. Every `|safe`, `autoescape off`, `mark_safe`, `Markup`, `format_html` with a dynamic format string: data origin and sanitizer on the write path.
2. Jinja2 environments created in code: `autoescape` set? (`select_autoescape` for `.html`).
3. `href`/`src` from user fields in templates - scheme check?
4. Base templates: third-party scripts (SRI), inline scripts with template values (use `json_script`), `on*` handlers.
5. Redirect views using `next`/`return_url` without `url_has_allowed_host_and_scheme`.
6. Admin customizations (`list_display` callables returning `mark_safe` with user data - admins of a SaaS are tenants).
7. Email templates rendering user fields as HTML.

## Stack-specific false positives
- `mark_safe` on constants (icons, static markup) - Info.
- `format_html("<b>{}</b>", user)` - args are escaped; safe. Only the format string matters.
- `{{ x|safe }}` where `x` is produced by `nh3.clean`/`bleach.clean` on save - justified, Info.
- `JsonResponse(..., safe=False)` - unrelated to XSS.
- `{{ x|escapejs }}` inside a quoted JS string - correct.

## Tooling
- `bandit -r <dir>` (B308 mark_safe, B703 django_mark_safe, B701 jinja2_autoescape_false).
- `semgrep --config p/django --config p/flask --config p/python` (`django-mark-safe`, `jinja2-autoescape-false`, `flask-markup`).
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/python-django.json`; `scan_html_scripts.py` over `templates/**` and `static/**`.

## References
Django "Security in Django" (XSS), `json_script` docs; Jinja2 autoescaping docs; OWASP XSS Prevention Cheat Sheet; OWASP SRI. CWE-79, CWE-80, CWE-601, CWE-829; ASVS 5.3.1-5.3.3, 14.2.3; OWASP A03:2021, A05:2021.
