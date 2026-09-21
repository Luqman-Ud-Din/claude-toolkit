# .NET / C# reference for audit-frontend-xss-and-dom-safety

XSS is mostly a client topic; this file covers what the .NET side contributes:
server-rendered HTML (Razor Pages/MVC/Blazor), API responses that carry HTML,
and the server-side sanitization a frontend bypass may rely on.

## Stack markers
`*.csproj`, `*.cshtml` (Razor views/pages), `*.razor` (Blazor), `wwwroot/**`, `Views/Shared/_Layout.cshtml`. Pure Web API projects (no `Views/`) usually only matter for "does the API sanitize on write" and for HTML-returning endpoints.

## Where the relevant code lives
`Views/**/*.cshtml`, `Pages/**/*.cshtml`, `Areas/**`, `*.razor`, `_Layout.cshtml`/`_Host.cshtml` (third-party scripts, inline init scripts), `wwwroot/js/**` (raw DOM code), controllers returning `Content(html, "text/html")` or `ContentResult`, email/PDF template builders (`StringBuilder` HTML), `TagHelpers/`, `HtmlHelpers/`, any `HtmlSanitizer`/`Ganss.XSS` usage (that is the server-side sanitizer a client bypass might cite).

## Dangerous / interesting APIs and patterns
- Bypasses (BYPASS/SSR): `@Html.Raw(x)`, `@(new HtmlString(x))`, `new HtmlString(`, `IHtmlContent` built from strings, `MarkupString` in Blazor (`@((MarkupString)x)`), `Html.Encode` missing in `TagBuilder.InnerHtml.AppendHtml(x)` (vs `.Append(x)` which encodes), `HtmlString.Create`, `@:` raw lines with concatenated input, `Response.WriteAsync("<html>..." + x)`, `Content($"<div>{x}</div>", "text/html")`, `ViewBag.Message = Request.Query["m"]` rendered with `@Html.Raw`.
- Script context: `<script>var data = @Html.Raw(Json.Serialize(model));</script>` - `Json.Serialize` (System.Text.Json) escapes `<` by default only with `JavaScriptEncoder.UnsafeRelaxedJsonEscaping` **not** set; Newtonsoft `JsonConvert.SerializeObject` does not escape `</script>` - breakout.
- Attribute context: `<a href="@Model.Url">` - Razor encodes but does not check scheme (`javascript:` survives encoding); `<a href="javascript:@x">`.
- Blazor: `MarkupString`, `ElementReference` + JS interop `eval`, `IJSRuntime.InvokeAsync("eval", x)`, `JS.InvokeVoidAsync("setInnerHtml", ...)` helpers in `wwwroot/js`.
- Raw JS in `wwwroot/js`: `innerHTML =`, `document.write(`, `$(...).html(`, `eval(`.
- SRI/INLINE: `_Layout.cshtml` `<script src="https://cdn...">` without `integrity`; `asp-fallback-*` tag helpers with `asp-fallback-test` inline; inline `<script>` blocks setting `window.__config`; `@section Scripts` inline handlers; CSP (`Content-Security-Policy` header) owned by `audit-security-headers-and-middleware`.
- Sanitizers: `Ganss.Xss.HtmlSanitizer` (`new HtmlSanitizer().Sanitize(x)`), `Microsoft.Security.Application.Sanitizer` (AntiXSS, legacy). A frontend "justified bypass because the API sanitizes" is only justified if one of these runs on the **write** path (`Create`/`Update` DTO handling), not on read.

## What "good" looks like
```cshtml
@* Razor encodes by default *@
<p>@Model.Comment.Body</p>

@* HTML needed: sanitize server-side first and say why *@
@* Justified: help articles authored in the CMS may contain tables; HtmlSanitizer allow-list in HelpService. *@
<div>@Html.Raw(Model.SanitizedHtml)</div>

@* Data for scripts: encode for the JS context *@
<script>window.__data = @Json.Serialize(Model.Data);</script>  @* System.Text.Json default encoder escapes < > & *@

@* Third-party scripts with SRI *@
<script src="https://cdn.example.com/lib.min.js" integrity="sha384-..." crossorigin="anonymous"></script>
```
```csharp
// API write path sanitization the SPA can rely on
var sanitizer = new HtmlSanitizer(); sanitizer.AllowedTags.Clear(); sanitizer.AllowedTags.UnionWith(new[]{"p","b","i","a","ul","li"});
entity.Description = sanitizer.Sanitize(dto.Description);
```

## Manual trace checklist
1. Every `Html.Raw`/`HtmlString`/`MarkupString`: model property source (user field vs resource string).
2. `_Layout`/`_Host`: third-party scripts (SRI), inline config scripts (CSP), `Json.Serialize` inside `<script>`.
3. Any controller action returning `text/html` from a string; error pages echoing the path or query (`UseDeveloperExceptionPage` in prod belongs to headers skill, but echoing is XSS).
4. If the SPA claims "the API sanitizes": find the sanitizer on the write path in `*Manager`/`*Service` for the exact field.
5. Email/PDF HTML builders with user fields (HTML injection in email is phishing; report Medium).

## Stack-specific false positives
- `@Html.Raw(Localizer["Key"])` with resource strings only developers edit - Info.
- `@Html.Raw(Json.Serialize(x))` with System.Text.Json default encoder (escapes `<`) - safe; Newtonsoft without `StringEscapeHandling.EscapeHtml` is not.
- `Html.Raw` on server-generated markup with no user data (pagination links) - Info.
- `MarkupString` over a constant SVG.

## Tooling
- `SecurityCodeScan` (SCS0029 XSS), `Microsoft.CodeAnalysis.NetAnalyzers` CA3002 (XSS), CA3003 (file path in `Html.Raw`?) - run via `dotnet build` with analyzers enabled.
- `semgrep --config p/csharp` (`razor-use-of-html-raw`, `razor-template-injection`).
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/dotnet.json`; `scan_html_scripts.py` over `Views/**` and `wwwroot/**`.

## References
Microsoft "Prevent Cross-Site Scripting (XSS) in ASP.NET Core"; Blazor `MarkupString` docs; OWASP XSS Prevention Cheat Sheet; OWASP SRI. CWE-79, CWE-80, CWE-829; ASVS 5.3.1-5.3.3, 14.2.3; OWASP A03:2021, A05:2021.
