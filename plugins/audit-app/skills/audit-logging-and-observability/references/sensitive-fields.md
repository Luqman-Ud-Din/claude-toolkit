# Sensitive field names for audit-logging-and-observability

`scripts/log_scan.py` classifies each identifier in a log call's arguments with
`audit-sensitive-data-catalog` (`classify_name`). The catalog owns the names; this
file owns how its answer maps to a log category and a severity. Add a missing name
to `$AUDIT_CORE_ROOT/skills/audit-sensitive-data-catalog/references/catalog.json`, never to the script.

## Category mapping

| Category | Catalog result | Examples | Severity when logged |
|---|---|---|---|
| credentials | `category: secret`, or subcategory `password`, `security-answer`, `pin` | password, passphrase, client_secret, api_key, private_key, connectionString, jwtKey | Critical |
| tokens | subcategory `token`, `session`, `cookie`, `otp` | token, access_token, refresh_token, jwt, bearer, authorization, cookie, sessionId, otp, mfaCode | Critical |
| financial | `category: financial` | cardNumber, pan, cvv, iban, accountNumber, salary | Critical |
| personal | any other sensitive category (identifier, contact, health, special-category) | ssn, nationalId, cnic, passport, dob, email, phone, address, firstName, ipAddress | High |
| whole-object | not a catalog check: `WHOLE_OBJECT_RX` in the script | body, request.body, req.body, request.data, payload, headers, dto, model, form | depends on shape - trace it |

Only names whose catalog `form` is `plain` are reported: hashed, encrypted and masked
forms (`passwordHash`, `encryptedSsn`, `maskedPan`, `cardLast4`) are not.

Why the split:
- **Credentials, tokens, financial** - one leaked value is directly usable (log in,
  replay a session, charge a card), and PCI DSS forbids storing sensitive
  authentication data such as CVV at all. Critical.
- **Personal** - regulated (GDPR and local data-protection laws) and useful for
  phishing and account takeover, but not directly a credential. High. Downgrade to
  Medium when only a user id or a hashed/truncated value is logged and the finding is
  about consistency.
- **Whole-object** - the statement logs something that *may* contain the above.
  Open the type: the login DTO, `req.body` on `/auth/login`, `headers` (always
  carries `Authorization`/`Cookie` when present). Rate by what it actually carries;
  if the shape cannot be established, use `confidence: likely` at High.

## Name normalisation

The catalog normalises identifiers (contract:
`$AUDIT_CORE_ROOT/skills/audit-sensitive-data-catalog/references/sensitive-data-catalog-contract.md`):
1. Split camelCase and PascalCase, treat `_`, `-`, `.` and spaces as separators, then
   lower-case (`refreshToken`, `refresh_token` and `RefreshToken` all match).
2. A sensitive form matches adjacent tokens anywhere in the name (`user.password`,
   `newPassword`, `X-Api-Key`).
3. A metadata, structural or reference word after the name (`passwordPolicy`,
   `tokenExpiry`, `emailSent`, `tokenInterceptor`, `cardId`), or a boolean or verb prefix
   before it (`hasPassword`, `forgotPassword`, `AddJwtBearer`), rules the name out.
4. Whole-object names are matched by the script, as a whole identifier or dotted path
   (`req.body`, `request.data`, `loginDto`, `model`), not as a substring of `bodyTemplate`.

## False positives

- **Message constants**: `logger.info("password reset email sent", userId)` - the word
  is in the literal message and no value is logged. The script ignores names that
  occur only inside the quoted message; confirm by reading the arguments.
- **Metadata about the secret, not the secret**: `passwordPolicy`, `passwordLength`,
  `passwordExpiresAt`, `tokenExpiry`, `tokenType`, `sessionTimeout`, `cardType`,
  `cookieName`, `emailVerified`.
- **Explicitly hashed or masked values**: `passwordHash`, `emailHash`, `cardLast4`,
  `maskedPan` - not reported by the script; fine unless the "hash" is reversible or the
  raw value sits next to it.
- **Identifiers**: `sessionId` is reported as a token. Downgrade it when it is only an
  opaque correlation value; keep it when it is the session cookie value used for authentication.
- **IP and MAC addresses** (`ipAddress`, `macAddress`) are reported as personal data, because
  they are personal data under GDPR; rate them by retention and access instead of dropping them.
- **Test fixtures and seed scripts** under `tests/`, `__tests__`, `*.spec.*`, `seed*`.

## Redaction snippets

**Serilog**
```csharp
.Destructure.UsingAttributes()          // [NotLogged] Password, [LogMasked(ShowLast = 4)] CardNumber
.Destructure.ByTransforming<LoginRequest>(r => new { r.Email })
```

**Logback (logstash-logback-encoder)**
```xml
<jsonGeneratorDecorator class="net.logstash.logback.mask.MaskingJsonGeneratorDecorator">
  <defaultMask>[REDACTED]</defaultMask>
  <paths>password,passwd,secret,token,access_token,refresh_token,authorization,cookie,cvv,card_number</paths>
</jsonGeneratorDecorator>
```

**pino**
```ts
pino({ redact: { paths: ['*.password', '*.token', '*.refreshToken', 'req.headers.authorization',
                         'req.headers.cookie', '*.cardNumber', '*.cvv'], censor: '[REDACTED]' } });
```

**winston**
```ts
const SENSITIVE = /^(password|passwd|pwd|secret|token|access_?token|refresh_?token|authorization|cookie|cvv|card_?number)$/i;
const redact = winston.format((info) =>
  Object.assign(info, JSON.parse(JSON.stringify(info, (k, v) => (SENSITIVE.test(k) ? '[REDACTED]' : v)))));
```

**structlog**
```python
SENSITIVE = {"password", "passwd", "pwd", "secret", "token", "access_token", "refresh_token",
             "authorization", "cookie", "cvv", "card_number"}
def redact(_, __, ev):
    return {k: ("[REDACTED]" if k.lower() in SENSITIVE else v) for k, v in ev.items()}
```

**Python logging Filter**
```python
class RedactFilter(logging.Filter):
    PATTERN = re.compile(r"(?i)(password|token|secret|authorization)(['\"]?\s*[:=]\s*['\"]?)[^'\",\s}]+")
    def filter(self, record):
        record.msg = self.PATTERN.sub(r"\1\2[REDACTED]", str(record.msg))
        return True
```

Redaction is a safety net. The remediation in a finding is still: do not pass the
object or field to the logger; log an id instead. After a confirmed leak, purge the
affected log indices and rotate the exposed credentials or tokens.
