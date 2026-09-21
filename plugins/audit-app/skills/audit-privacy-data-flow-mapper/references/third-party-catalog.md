# Third-party catalog

`scripts/pii_scan.py` resolves outbound hosts and SDK identifiers to a vendor
using `references/third-party-catalog.json` (same content as the table below;
the JSON is what the script reads). Add a vendor by appending an object
`{"name", "category", "domains": [...], "sdk": [...]}` to the JSON. Hosts that
match nothing are listed under `unresolved_hosts` in the inventory and must be
classified by hand (internal service, partner API, or a vendor to add here).

| Vendor | Category | Domains | SDK / identifiers | Typical data received |
|---|---|---|---|---|
| Mailchimp / Mandrill | marketing | api.mailchimp.com, mandrillapp.com | MailchimpClient, mailchimp_marketing, @mailchimp/mailchimp_marketing | email, name, tags, merge fields |
| HubSpot | marketing | api.hubapi.com | HubSpot, hubspot | email, name, phone, company |
| SendGrid | email | api.sendgrid.com | SendGridClient, @sendgrid/mail | recipient email, template data |
| Mailgun | email | api.mailgun.net | mailgun | recipient email, template data |
| Amazon SES | email | ses.amazonaws.com | AmazonSimpleEmailService, SESClient | recipient email |
| Twilio | sms | api.twilio.com | TwilioClient, MessageResource | phone, message body (OTP, names) |
| Vonage / Nexmo | sms | api.nexmo.com, api.vonage.com | Vonage, nexmo | phone, message body |
| Stripe | payments | api.stripe.com | StripeClient, stripe | email, name, address, card (tokenised) |
| PayPal | payments | api.paypal.com, api-m.paypal.com | PayPal | email, name, address |
| Segment | analytics | api.segment.io | analytics-node, @segment/analytics | user id, traits (email, name), events |
| Mixpanel | analytics | api.mixpanel.com | mixpanel | distinct id, profile properties |
| Amplitude | analytics | api.amplitude.com | amplitude | user id, properties |
| Google Analytics / GTM | analytics | google-analytics.com, googletagmanager.com | gtag, ga(, dataLayer | client id, page URLs, custom dimensions, IP |
| Firebase | analytics/push | firebaseio.com, fcm.googleapis.com | firebase, FirebaseAnalytics, FirebaseMessaging, @angular/fire | device tokens, events, user properties |
| PostHog | analytics | app.posthog.com, eu.posthog.com | posthog | distinct id, events, session replay |
| Hotjar | analytics | hotjar.com | hj( | session recordings (may capture typed PII) |
| Microsoft Clarity | analytics | clarity.ms | clarity( | session recordings |
| Sentry | error-tracking | sentry.io | Sentry, @sentry/, sentry_sdk | stack traces, request data, user context (email/IP if set) |
| Bugsnag | error-tracking | notify.bugsnag.com | Bugsnag | as Sentry |
| Rollbar | error-tracking | api.rollbar.com | Rollbar | as Sentry |
| Application Insights | error-tracking/analytics | applicationinsights.azure.com, dc.services.visualstudio.com | TelemetryClient, appInsights | requests, traces, custom properties |
| Datadog | logging/monitoring | datadoghq.com | datadog, ddtrace | logs (everything in them), traces |
| New Relic | logging/monitoring | newrelic.com | newrelic | logs, traces |
| Intercom | support | api.intercom.io, widget.intercom.io | Intercom | email, name, conversation content |
| Zendesk | support | zendesk.com | Zendesk | email, name, tickets |
| Freshdesk | support | freshdesk.com | Freshdesk | email, name, tickets |
| Slack | messaging | hooks.slack.com | SlackClient, @slack/web-api, slack_sdk | whatever the alert text contains |
| Google Drive | storage | googleapis.com/drive | DriveService, Google.Apis.Drive | uploaded files (invoices, reports with names) |
| Google Maps | geolocation | maps.googleapis.com | @googlemaps | addresses, coordinates |
| Amazon S3 | storage | s3.amazonaws.com | AmazonS3Client, S3Client, @aws-sdk/client-s3 | uploaded files, exports, backups |
| Azure Blob Storage | storage | blob.core.windows.net | BlobServiceClient | uploaded files, exports, backups |
| Cloudinary | storage | api.cloudinary.com | cloudinary | images (avatars, documents) |
| Shopify | commerce | myshopify.com | ShopifySharp, shopify | customer name, email, address, orders |
| OpenAI | ai | api.openai.com | OpenAI, openai | prompt content (may include PII) |
| Anthropic | ai | api.anthropic.com | Anthropic, anthropic | prompt content |
| Auth0 | identity | auth0.com | Auth0 | email, name, login metadata, IP |
| Okta | identity | okta.com | Okta | as Auth0 |
| Microsoft Entra / Graph | identity | graph.microsoft.com, login.microsoftonline.com | GraphServiceClient | email, name, directory data |
| FBR (Pakistan tax) | government/tax | fbr.gov.pk | FbrInvoice, FBR | buyer name, NTN/CNIC, invoice lines |
| ZATCA (Saudi tax) | government/tax | zatca.gov.sa | Zatca, ZATCA | buyer name, VAT number, invoice lines |

## Categories and what the GDPR/SOC 2 skills do with them

- `marketing`, `analytics`, `support`: need consent or legitimate-interest
  assessment; must be on the processor list with a DPA; usually non-EU -> transfer
  mechanism (SCCs/DPF) is an organisational item.
- `email`, `sms`, `payments`, `identity`: usually necessary for the contract;
  still processors; check which fields are sent (minimisation).
- `error-tracking`, `logging/monitoring`: the sink for accidental PII (logs,
  request bodies, user context); retention settings live in the vendor console.
- `storage`: exports, backups, uploaded documents; erasure must reach them.
- `government/tax`: legal obligation basis; not a processor but a separate
  controller; document the transfer.
- `ai`: prompt content is a transfer; check the vendor's training/retention terms.

## Marking a host as internal

If an unresolved host is your own service (gateway, microservice, internal
API), say so in the report under *Not checked* -> "internal, not a third
party"; do not add internal hosts to the catalog.
