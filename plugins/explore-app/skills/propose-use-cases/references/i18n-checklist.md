# International-readiness checklist

Apply every item. Classify each as PRESENT (cite the BLD), PARTIAL (cite what
exists, state what is missing) or MISSING. Items marked *(market-dependent)*
need the target markets to be judged fully; classify them anyway and note the
dependency. The IDs are stable and appear in the output table.

## A. Money: currency, pricing, rounding

- **I18N-A1** Prices and amounts are stored with an explicit currency (ISO 4217) rather than an implied one.
- **I18N-A2** Multiple currencies can coexist: a tenant, customer or document can be in a currency other than the system default.
- **I18N-A3** Exchange rates are stored with source, date and rate, and historical documents keep the rate used at the time.
- **I18N-A4** Rounding rules are explicit and currency-aware (zero-decimal currencies such as JPY and KWD's three decimals; cash rounding where required, e.g. 0.05 in some markets).
- **I18N-A5** Tax-inclusive and tax-exclusive pricing are both supported and the display mode is configurable per market.
- **I18N-A6** Price lists or pricing tiers can vary by market, region or customer group.

## B. Tax and invoicing compliance

- **I18N-B1** Tax is calculated by rule (rate tables by jurisdiction, product category and date) rather than a single rate or a hard-coded per-country conditional. *(market-dependent)*
- **I18N-B2** Multiple tax types on one document (VAT/GST, withholding, excise, service charges) are representable.
- **I18N-B3** Tax registration numbers (VAT ID, GSTIN, NTN, TRN) are stored, validated per format, and printed where required.
- **I18N-B4** Invoice numbering satisfies sequential/gapless requirements where a market mandates them, per legal entity or branch. *(market-dependent)*
- **I18N-B5** Mandatory invoice content by jurisdiction (seller/buyer identifiers, tax breakdown per rate, QR code, language, currency) is configurable. *(market-dependent)*
- **I18N-B6** E-invoicing / fiscalisation submission to the tax authority (e.g. FBR, ZATCA, SDI, KSeF, Peppol) is supported or abstracted for the target markets. *(market-dependent)*
- **I18N-B7** Credit notes and corrective documents follow local rules rather than editing or deleting an issued invoice.
- **I18N-B8** Document retention periods and immutability of issued fiscal documents are enforced.

## C. Locale-aware formatting

- **I18N-C1** Dates and times are displayed in the viewer's locale and calendar conventions (day/month order, 12/24h; Hijri or other calendars where used).
- **I18N-C2** Numbers use locale separators and digit systems (decimal comma, Arabic-Indic digits, Indian grouping).
- **I18N-C3** Addresses are stored as structured, country-aware fields (no fixed postcode regex, optional state/region, variable line count) and formatted per country.
- **I18N-C4** Personal names are stored without assuming a first/last split, ordering or character set.
- **I18N-C5** Phone numbers are stored in E.164 with country code and validated per country, not by a single regex.
- **I18N-C6** Units of measure (weight, volume, length, temperature) are stored with the unit and convertible.

## D. Time zones and calendars

- **I18N-D1** Timestamps are stored with time zone (UTC or offset), not server-local naive time.
- **I18N-D2** Each tenant, branch or user has a time zone, and business cut-offs (day close, reporting periods, due dates) use it rather than the server's.
- **I18N-D3** Scheduled jobs and reminders account for the recipient's time zone and DST transitions.
- **I18N-D4** Working days, weekends and public holidays are configurable per market (Friday/Saturday weekends, local holidays).
- **I18N-D5** Fiscal year start is configurable per legal entity.

## E. Translations and RTL

- **I18N-E1** All user-facing strings are externalised and translatable, including server-generated messages, e-mails, and printed documents.
- **I18N-E2** Right-to-left layout is supported end to end (UI, PDFs, e-mails) for RTL target languages.
- **I18N-E3** Business data (product names, categories, document templates) can be stored in more than one language, not only UI chrome.
- **I18N-E4** Locale is selected per user or tenant and propagated to the backend (for messages, formatting, documents), not inferred only from the browser.
- **I18N-E5** Sorting, searching and case-folding are locale- and Unicode-aware (collation, diacritics, non-Latin scripts).

## F. Data residency, privacy and consent

- **I18N-F1** Data residency: tenant data can be hosted in, or restricted to, a required region; the deployment model supports more than one region. *(market-dependent)*
- **I18N-F2** Privacy regime obligations (GDPR, UK GDPR, PDPL in KSA, PDPB/DPDP in India, LGPD, CCPA/CPRA, and similar) are mapped to features: lawful-basis and consent capture, data subject access and export, erasure/anonymisation, retention schedules. *(market-dependent)*
- **I18N-F3** Cross-border transfer controls: sub-processors and regions are documented, and transfers are configurable per tenant.
- **I18N-F4** Audit logging of access to personal and financial data, with retention and immutability.
- **I18N-F5** Security and breach-notification requirements of the target regimes are supported operationally (incident records, notification timelines).

## G. Payments by region

- **I18N-G1** Payment provider is abstracted so that regional providers and methods can be added without changing business code. *(market-dependent)*
- **I18N-G2** Locally expected methods are available per market (cards, bank transfer/SEPA, wallets such as JazzCash/EasyPaisa, STC Pay, mada, UPI, iDEAL, PIX, cash-on-delivery). *(market-dependent)*
- **I18N-G3** Settlement currency, fees and reconciliation are tracked per provider and currency.
- **I18N-G4** Refund and chargeback flows exist and respect local time limits and rules.
- **I18N-G5** Strong customer authentication / 3-D Secure and local card-scheme rules are handled where mandated.

## H. Shipping, logistics and units

- **I18N-H1** Shipping addresses and carriers vary by country; carrier integration is abstracted or configurable per market.
- **I18N-H2** Customs and cross-border documentation (HS codes, incoterms, declared values) are supported where goods cross borders.
- **I18N-H3** Delivery time estimates account for local calendars and time zones.

## I. Legal documents by jurisdiction

- **I18N-I1** Terms of service, privacy policy, cookie/consent notices and contracts are versioned per jurisdiction and language, and acceptance is recorded.
- **I18N-I2** Printed and e-mailed documents (invoices, receipts, statements) use jurisdiction-specific templates and mandatory wording. *(market-dependent)*
- **I18N-I3** Consumer-protection requirements (return periods, warranty text, pricing display rules) are configurable per market. *(market-dependent)*

## J. Customer support and operations

- **I18N-J1** Support hours, channels and languages are defined per market, and the product surfaces the right contact per locale.
- **I18N-J2** Notifications (e-mail, SMS, push) use market-appropriate providers, sender IDs and languages; SMS providers and templates are per country.
- **I18N-J3** Status pages, SLAs and maintenance windows are communicated in local time and language.

## K. Regional feature toggles and configuration

- **I18N-K1** Features can be enabled or disabled per market, tenant or plan without code changes (feature toggles with a regional dimension).
- **I18N-K2** Market-specific configuration (tax tables, document formats, payment methods, legal text) lives in data or config, not in code branches.
- **I18N-K3** A new market can be onboarded by configuration plus a documented checklist rather than a code release.
- **I18N-K4** Reporting and analytics can segment by market, currency and region, and consolidate across them at a defined rate.
