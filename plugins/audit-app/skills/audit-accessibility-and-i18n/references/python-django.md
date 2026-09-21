# Python / Django reference for audit-accessibility-and-i18n

This skill audits the user-facing layer. Django renders HTML by default, so
its templates are first-class targets for the WCAG checks; it also owns
locale negotiation (`LocaleMiddleware`), translation (`gettext`), and formatting
(`USE_L10N`, `localize`). Flask/FastAPI (Jinja2) follow the same shape with
`Flask-Babel`.

## Stack markers

`manage.py`, `settings.py` with `USE_I18N`, `LANGUAGES`, `LOCALE_PATHS`,
`django.middleware.locale.LocaleMiddleware`; `locale/<lang>/LC_MESSAGES/django.po`;
`templates/**/*.html` with `{% load i18n %}`; DRF serializers with `error_messages`.

## Where the relevant code lives

`templates/**` (`{% trans %}`, `{% blocktrans %}`, `{{ value|date }}`, `{{ value|localize }}`),
`base.html` (`<html lang="{{ LANGUAGE_CODE }}" dir=...>`, skip link, `<main>`), `forms.py`
(labels, `help_text`, `error_messages`), `models.py` (`verbose_name`), `views.py`/`serializers.py`
(messages), `settings.py` (`USE_I18N`, `USE_L10N` (removed in 5.0; always on), `LANGUAGES`,
`FORMAT_MODULE_PATH`), `locale/`, email templates, export code (openpyxl, reportlab, weasyprint).

## Dangerous / interesting APIs and patterns (this skill's slice only)

- Templates: `<input>` rendered by hand without `<label for="{{ field.id_for_label }}">`;
  `{{ form.as_p }}` is labelled but hand-written fields often are not; `<img>` without `alt`;
  literal text instead of `{% trans %}`; `<html>` without `lang="{{ LANGUAGE_CODE }}"`;
  custom modals without `role="dialog"`; `{% if field.errors %}` rendered without `role="alert"`
  or `aria-describedby`.
- `USE_I18N = False`; `LocaleMiddleware` missing (locale never negotiated); `LANGUAGE_CODE`
  hard-coded with no `LANGUAGES`; `gettext` not used in `forms.py`/`views.py`/`models.py`
  (`label="Email"`, `messages.success(request, "Saved")`, `ValidationError("Invalid quantity")`)
  - wrap with `_()` / `gettext_lazy`.
- `gettext` used with string formatting before translation (`_("%d items" % n)`) or f-strings
  (`_(f"{n} items")`) - untranslatable; plurals via `ngettext` missing.
- Formatting: `value.strftime("%d/%m/%Y")` or `"%.2f" % amount` for display instead of the
  `date`/`floatformat`/`localize` filters with `USE_THOUSAND_SEPARATOR`; `{{ value|date:"d/m/Y" }}`
  fixed pattern instead of `SHORT_DATE_FORMAT`; `float(request.POST["qty"])` on comma-decimal
  locales (`forms.DecimalField` handles `localize=True`).
- DRF: `error_messages` literal, `ValidationError("...")` without `_()`, dates serialized with a
  custom format instead of ISO-8601.
- RTL: `LANGUAGE_BIDI` unused; templates with `text-align: left`, `margin-left` etc.;
  `{% get_current_language_bidi as LANGUAGE_BIDI %}` missing where `dir` should be set.
- Emails/exports using the server locale (`translation.activate` not called in Celery tasks);
  PDFs without RTL fonts/shaping for Arabic/Urdu.

## What "good" looks like

```python
# settings.py
USE_I18N = True
LANGUAGES = [("en", "English"), ("ar", "العربية"), ("ur", "اردو")]
LOCALE_PATHS = [BASE_DIR / "locale"]
MIDDLEWARE = [..., "django.contrib.sessions.middleware.SessionMiddleware",
              "django.middleware.locale.LocaleMiddleware", "django.middleware.common.CommonMiddleware", ...]
# forms.py
class CheckoutForm(forms.Form):
    email = forms.EmailField(label=_("Email"), error_messages={"invalid": _("Enter a valid email")})
# views.py
messages.success(request, ngettext("%(n)d item added", "%(n)d items added", n) % {"n": n})
```
```django
{% load i18n %}{% get_current_language as LANGUAGE_CODE %}{% get_current_language_bidi as LANGUAGE_BIDI %}
<html lang="{{ LANGUAGE_CODE }}" dir="{% if LANGUAGE_BIDI %}rtl{% else %}ltr{% endif %}">
<a class="skip-link" href="#main">{% trans "Skip to content" %}</a>
<label for="{{ form.email.id_for_label }}">{{ form.email.label }}</label>
{{ form.email }}
{% if form.email.errors %}<p id="{{ form.email.id_for_label }}-err" role="alert">{{ form.email.errors|striptags }}</p>{% endif %}
<img src="{{ product.image.url }}" alt="{{ product.name }}">
<p>{{ order.total|floatformat:2 }} - {{ order.created|date:"SHORT_DATE_FORMAT" }}</p>
```

## Manual trace checklist

1. Run `template_scan.py` over `templates/` (Django templates are HTML with tags; `{% trans %}`
   and `{% blocktrans %}` are recognized as translated) and apply the WCAG checklist.
2. Trace one form error from `forms.py` to the page: translated, announced (`role="alert"`),
   linked (`aria-describedby`)?
3. Locale negotiation: `LocaleMiddleware` order (after Session, before Common), `LANGUAGES`,
   `locale/` present with compiled `.mo` files.
4. One API response with a date and an amount: ISO and raw?
5. Celery/email code: `translation.override(user.language)` used?

## Stack-specific false positives

- `{{ form.as_p }}` / `{{ form }}`: labelled by Django; only hand-rendered fields need checking.
- `strftime` used for filenames/log lines: not display.
- `_()` around a string with `%(name)s` placeholders and formatting *after* translation: correct.

## Tooling

`python manage.py makemessages -l ar --dry-run` (counts marked strings; compare with
`template_scan.py`), `python manage.py compilemessages`, `django-admin check`; `pa11y` /
`@axe-core/cli` against `runserver` routes via `scripts/axe_runner.py`; `flake8-i18n` or a
grep for `messages\.(success|error)\(request, "` for literals.

## Deferred to sibling skills

`TIME_ZONE`/`USE_TZ` correctness: `audit-datetime-and-timezone`. `|safe` / `mark_safe`:
`audit-frontend-xss-and-dom-safety`.

## References

Django i18n: https://docs.djangoproject.com/en/stable/topics/i18n/translation/; format
localization: https://docs.djangoproject.com/en/stable/topics/i18n/formatting/; Django forms
accessibility: https://docs.djangoproject.com/en/stable/topics/forms/#rendering-fields-manually;
WCAG 2.2: https://www.w3.org/TR/WCAG22/
