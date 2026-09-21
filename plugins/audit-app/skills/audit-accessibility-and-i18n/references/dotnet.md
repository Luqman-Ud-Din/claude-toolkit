# .NET / C# reference for audit-accessibility-and-i18n

This skill audits the user-facing layer. An ASP.NET Core backend matters when it
(a) renders HTML itself (Razor Pages, MVC views, Blazor) - then the a11y checks
apply to `.cshtml`/`.razor` exactly as to SPA templates, or (b) produces
user-facing text and formatted values that the SPA displays (validation
messages, emails, PDF/Excel exports, API error strings), or (c) decides the
request culture. Check those; defer everything else.

## Stack markers

`*.csproj` with `Microsoft.AspNetCore.App`; `Pages/*.cshtml` / `Views/**/*.cshtml` (server-rendered),
`*.razor` (Blazor), `Resources/*.resx` + `IStringLocalizer` (localization present),
`AddLocalization`/`UseRequestLocalization` in `Program.cs`.

## Where the relevant code lives

`Program.cs` (`AddLocalization`, `AddRequestLocalization`, `SupportedCultures`,
`RequestCultureProviders`), `Resources/**/*.resx`, `Views/Shared/_Layout.cshtml` (`<html lang>`,
skip link, `<main>`), `Pages/**`, validation attributes on DTOs (`[Required(ErrorMessage = "...")]`),
`*Manager.cs`/`*Service.cs` returning message strings, export code (EPPlus, PDF) formatting
dates/numbers, email templates.

## Dangerous / interesting APIs and patterns (this skill's slice only)

- Razor/Blazor templates: `<input asp-for>` without `<label asp-for>`; `<img>` without `alt`;
  hand-rolled modals without `role="dialog"`/focus handling; `<html>` without `lang="@culture"`;
  hard-coded text instead of `@Localizer["Key"]` / `@SharedLocalizer` / `<resource>`.
- Validation and API messages hard-coded in English: `[Required(ErrorMessage = "Email is required")]`
  without `ErrorMessageResourceType`, `return BadRequest("Invalid quantity")`, exceptions whose
  `Message` is shown to users. The SPA cannot translate what the server invents.
- Culture: no `UseRequestLocalization`; `CultureInfo.CurrentCulture` set from a hard-coded
  `"en-US"`; `DateTime.Now.ToString("dd/MM/yyyy")` or `.ToString("N2")` with the server culture
  in API responses (the API should return ISO 8601 and raw numbers; the client formats);
  `decimal.Parse(input)` without `CultureInfo.InvariantCulture` on user input from an
  Arabic/German locale (comma decimal separator).
- Exports (EPPlus/PDF) formatting dates/numbers with the server culture instead of the user's;
  RTL not set in generated PDFs (`RunDirection`) for Arabic/Urdu users.
- Pluralized strings built with `$"{count} item(s)"`.
- Emails/SMS with English-only text for a multilingual user base (`SMSLibrary`, notification
  templates).

## What "good" looks like

```csharp
builder.Services.AddLocalization(o => o.ResourcesPath = "Resources");
var cultures = new[] { "en", "ar", "ur" };
app.UseRequestLocalization(new RequestLocalizationOptions()
    .SetDefaultCulture("en").AddSupportedCultures(cultures).AddSupportedUICultures(cultures));
// API: return data, not formatted text
return Ok(new { total = order.Total, createdAt = order.CreatedAt.ToString("o"), currency = "PKR" });
// Validation with resources
[Required(ErrorMessageResourceType = typeof(Res.Validation), ErrorMessageResourceName = "EmailRequired")]
// Parsing user input
decimal.TryParse(text, NumberStyles.Number, CultureInfo.GetCultureInfo(userCulture), out var qty);
```
```cshtml
<html lang="@CultureInfo.CurrentUICulture.Name" dir="@(CultureInfo.CurrentUICulture.TextInfo.IsRightToLeft ? "rtl" : "ltr")">
<label asp-for="Email">@Localizer["Email"]</label><input asp-for="Email" autocomplete="email">
<span asp-validation-for="Email" role="alert"></span>
```

## Manual trace checklist

1. Does the backend render HTML? If yes, run `template_scan.py` over `Views/`, `Pages/`, and
   `.razor` files (it handles `.cshtml`/`.razor` as HTML) and apply the WCAG checklist.
2. Trace one validation error from DTO attribute to the screen: where is the text created, is it
   localizable, does the SPA show it verbatim?
3. Request culture: where does it come from (header, cookie, user profile)? Is it applied to
   exports and emails?
4. One API response with a date and a money amount: ISO string and raw number, or pre-formatted?

## Stack-specific false positives

- `CultureInfo.InvariantCulture` for *storage/serialization* is correct; it is only wrong for
  display to the user.
- Log messages and exception messages that never reach users: not findings.
- `[Required]` without a message: ASP.NET produces a default English message - still a finding
  if users see it, but Low.

## Tooling

`dotnet build` with `Microsoft.CodeAnalysis.NetAnalyzers` CA1305 (specify IFormatProvider) and
CA1304 (specify CultureInfo) enabled: `<AnalysisMode>AllEnabledByDefault</AnalysisMode>` or
`dotnet_diagnostic.CA1305.severity = warning` in `.editorconfig`; count warnings as evidence.
`ResXResourceReader`/`resx` diff between cultures for missing keys.

## Deferred to sibling skills

Time zone correctness of stored values: `audit-datetime-and-timezone`. Output encoding of
user strings in Razor: `audit-frontend-xss-and-dom-safety`.

## References

ASP.NET Core localization: https://learn.microsoft.com/aspnet/core/fundamentals/localization;
Razor accessibility (tag helpers `asp-for` labels): https://learn.microsoft.com/aspnet/core/mvc/views/working-with-forms;
WCAG 2.2: https://www.w3.org/TR/WCAG22/; CA1305: https://learn.microsoft.com/dotnet/fundamentals/code-analysis/quality-rules/ca1305
