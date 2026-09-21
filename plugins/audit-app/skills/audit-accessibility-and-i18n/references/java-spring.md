# Java / Spring reference for audit-accessibility-and-i18n

This skill audits the user-facing layer. A Spring backend matters when it
renders HTML (Thymeleaf, JSP, Freemarker), produces user-facing text
(validation messages, API errors, emails, exports), or resolves the locale.
Check those; defer everything else.

## Stack markers

`pom.xml`/`build.gradle` with `spring-boot-starter-thymeleaf` / `spring-boot-starter-web`;
`src/main/resources/templates/**/*.html` (Thymeleaf), `messages*.properties` (localization
present), `LocaleResolver` / `LocaleChangeInterceptor` beans, `spring.web.locale` /
`spring.messages.basename` properties.

## Where the relevant code lives

`templates/**` (`th:text`, `#{key}` message expressions, `layout.html` with `<html lang>`),
`messages.properties` + `messages_ar.properties` etc., `@Valid` DTOs with `@NotNull(message="...")`,
`@ControllerAdvice` error handlers building messages, `MessageSource` usage, export/report code
(Apache POI, JasperReports), mail templates, `WebMvcConfigurer` (`localeResolver`).

## Dangerous / interesting APIs and patterns (this skill's slice only)

- Thymeleaf: `<input th:field>` without `<label th:for>`; `<img th:src>` without `alt`/`th:alt`;
  literal text instead of `th:text="#{key}"`; `<html>` without `th:lang="${#locale.language}"`;
  hand-rolled modals without `role="dialog"` and focus handling.
- Validation messages hard-coded: `@NotBlank(message = "Email is required")` instead of
  `message = "{validation.email.required}"` resolved via `MessageSource`; `throw new
  IllegalArgumentException("Quantity must be positive")` surfaced to users; `ResponseEntity.badRequest().body("...")`.
- Locale: `Locale.setDefault(Locale.US)`; `AcceptHeaderLocaleResolver` absent (falls back to JVM
  default); `SimpleDateFormat("dd/MM/yyyy")` / `DateTimeFormatter.ofPattern(...)` without a
  `Locale` and used for display; `String.format("%.2f", amount)` with no `Locale`;
  `NumberFormat.getInstance()` (JVM default locale) for user output; `Double.parseDouble(userInput)`
  on locales with comma decimals.
- API responses returning pre-formatted dates/amounts (`"12/03/2024"`, `"1,234.50"`) instead of
  ISO-8601 and raw numbers; Jackson `@JsonFormat(pattern = "dd/MM/yyyy")` on API DTOs.
- Plurals: `count + " items"`; `MessageFormat` without `ChoiceFormat`/ICU plural.
- Exports and emails using the server locale; PDFs without RTL support for Arabic/Urdu.

## What "good" looks like

```java
@Bean LocaleResolver localeResolver() {
    var r = new AcceptHeaderLocaleResolver();
    r.setSupportedLocales(List.of(Locale.ENGLISH, new Locale("ar"), new Locale("ur")));
    r.setDefaultLocale(Locale.ENGLISH); return r;
}
// DTO
@NotBlank(message = "{validation.email.required}") String email;
// API: data, not text
record OrderDto(BigDecimal total, String currency, Instant createdAt) {}   // Jackson writes ISO-8601
// Display formatting only in the presentation layer
NumberFormat.getCurrencyInstance(locale).format(total);
DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM).withLocale(locale).format(date);
// Plurals via ICU4J
new com.ibm.icu.text.MessageFormat("{count, plural, one {# item} other {# items}}", locale).format(Map.of("count", n));
```
```html
<html th:lang="${#locale.language}" th:dir="${#locale.language == 'ar' or #locale.language == 'ur'} ? 'rtl' : 'ltr'">
<label th:for="email" th:text="#{checkout.email}">Email</label>
<input th:field="*{email}" type="email" autocomplete="email" aria-describedby="email-err">
<p id="email-err" role="alert" th:if="${#fields.hasErrors('email')}" th:errors="*{email}"></p>
```

## Manual trace checklist

1. Server-rendered HTML? Run `template_scan.py` over `templates/` (Thymeleaf files are HTML) and
   apply the WCAG checklist.
2. Trace one validation error from DTO annotation to the response body: localizable or literal?
3. Locale source: header, cookie, or user profile; applied to exports and emails?
4. One API response with a date and an amount: ISO and raw, or pre-formatted?

## Stack-specific false positives

- `DateTimeFormatter.ISO_*` for serialization: correct.
- `Locale.ROOT` for storage/normalization: correct.
- `messages.properties` present but `messages_ar.properties` incomplete: translation
  completeness, not a code defect; record under Not checked.

## Tooling

`mvn spotbugs:check` with `findsecbugs`/`sb-contrib` `DM_CONVERT_CASE`/`DM_DEFAULT_ENCODING`;
Error Prone `MissingLocale`? (not default) - use SonarQube rules S2135/S1166; a grep for
`SimpleDateFormat(` and `String.format(` in web/export packages gives counts for Evidence.

## Deferred to sibling skills

Time zone storage: `audit-datetime-and-timezone`. Thymeleaf `th:utext`/output encoding:
`audit-frontend-xss-and-dom-safety`.

## References

Spring i18n: https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-servlet/localeresolver.html;
Thymeleaf i18n: https://www.thymeleaf.org/doc/tutorials/3.1/usingthymeleaf.html#using-texts;
ICU4J MessageFormat: https://unicode-org.github.io/icu-docs/apidoc/released/icu4j/com/ibm/icu/text/MessageFormat.html;
WCAG 2.2: https://www.w3.org/TR/WCAG22/
