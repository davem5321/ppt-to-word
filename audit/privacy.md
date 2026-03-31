# Privacy Audit Report — Logfire Python SDK

**Date**: 2025-07-14  
**SDK Version**: 4.31.0  
**Auditor**: Privacy Audit Agent (Microsoft SDL–aligned)  
**Scope**: Open-source Python SDK (`logfire` package) — telemetry collection, credential management, CLI, auto-instrumentation, and data export to the Logfire SaaS backend. The closed-source Logfire platform (server, dashboard, storage) is **out of scope**.  
**References**: `audit/ARCHITECTURE.md`, `audit/THREAT_MODEL.md`, source code at `logfire/_internal/`

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Data Inventory](#data-inventory)
3. [Data Flow Summary](#data-flow-summary)
4. [Findings](#findings)
5. [Compliance Gap Analysis](#compliance-gap-analysis)
6. [Third-Party Data Sharing](#third-party-data-sharing)
7. [User Rights Assessment](#user-rights-assessment)
8. [Recommendations Summary](#recommendations-summary)

---

## Executive Summary

The Logfire Python SDK is an OpenTelemetry-based observability library that instruments Python applications and ships telemetry (traces, logs, metrics) to the Logfire SaaS backend. Because the SDK auto-instruments production frameworks—including OpenAI, Anthropic, FastAPI, Django, SQLAlchemy, and many others—it has a very large surface for capturing personal data from end users of those applications.

The primary privacy protection mechanism is a keyword-pattern scrubber (`logfire/_internal/scrubbing.py`). The audit found **one Critical, seven High, six Medium, and five Low findings**. The most serious issues are:

1. **OpenAI and Anthropic spans are completely exempt from scrubbing**—any PII in LLM prompts or model responses is transmitted verbatim to the Logfire backend.
2. **No opt-out toggle exists for LLM content capture** for `instrument_openai()` and `instrument_anthropic()`, unlike Google GenAI (which is opt-in) and PydanticAI (which has `include_content=False`).
3. **Critical span attributes—SQL queries, HTTP URLs, and exception messages—are in the scrubber's permanent `SAFE_KEYS` whitelist** and are never redacted, even when they contain user-supplied data.
4. **Failed export payloads are persisted unencrypted on disk** in the OS temp directory.

---

## Data Inventory

| # | Data Element | Collection Point | Stored Where | Transmitted To | Retention | Sensitivity | GDPR Personal Data? |
|---|---|---|---|---|---|---|---|
| D-01 | **LLM prompt text / messages** | `instrument_openai()`, `instrument_anthropic()`, `instrument_pydantic_ai()`, `instrument_openai_agents()` | In-memory spans, disk retry queue | Logfire backend | Until backend purge | **HBI** | Yes — may contain names, health info, PII |
| D-02 | **LLM model responses** | Same as D-01 | In-memory spans, disk retry queue | Logfire backend | Until backend purge | **HBI** | Yes — may contain or mirror user PII |
| D-03 | **SQL query text** | `instrument_sqlalchemy()`, `instrument_asyncpg()`, `instrument_psycopg()`, `instrument_sqlite3()` | In-memory spans, disk retry queue | Logfire backend | Until backend purge | **MBI–HBI** | Potentially (if queries embed user data) |
| D-04 | **HTTP request URLs & query strings** | `instrument_fastapi()`, `instrument_django()`, `instrument_flask()`, `instrument_starlette()`, `instrument_httpx()`, `instrument_requests()` | In-memory spans, disk retry queue | Logfire backend | Until backend purge | **MBI** | Yes — can contain user IDs, tokens, search terms |
| D-05 | **HTTP request/response headers** | Same frameworks above, when `capture_headers=True` | In-memory spans | Logfire backend | Until backend purge | **MBI–HBI** | Yes — Cookie, Authorization, etc. |
| D-06 | **HTTP request/response bodies** | `instrument_httpx()`, `instrument_aiohttp_client()` when `capture_request_body=True` or `capture_all=True` | In-memory spans | Logfire backend | Until backend purge | **HBI** | Yes — form data, JSON bodies with PII |
| D-07 | **Function arguments & return values** | `@logfire.instrument(extract_args=True)`, `install_auto_tracing()` | In-memory spans, disk retry queue | Logfire backend | Until backend purge | **MBI–HBI** | Yes — arguments may contain user data |
| D-08 | **Exception messages & stack traces** | All spans when exceptions occur | In-memory spans, disk retry queue | Logfire backend | Until backend purge | **MBI** | Potentially — validation errors often include user input |
| D-09 | **Pydantic model input/output data** | `instrument_pydantic(record='all')` | In-memory spans | Logfire backend | Until backend purge | **MBI–HBI** | Yes — model fields may be personal data |
| D-10 | **MCP tool call arguments & responses** | `instrument_mcp()` | In-memory spans | Logfire backend | Until backend purge | **MBI–HBI** | Yes — tool payloads may contain user data |
| D-11 | **Write tokens (LOGFIRE_TOKEN)** | `logfire.configure()`, env var, credential file | `.logfire/logfire_credentials.json` (disk) | Logfire backend (Authorization header) | Until rotated | **HBI** | No |
| D-12 | **User tokens (OAuth)** | `logfire auth` CLI | `~/.logfire/default.toml` (plaintext) | Logfire Management API | Until logout | **HBI** | No |
| D-13 | **Service name, version, environment** | `logfire.configure()` | In-memory resource attributes | Logfire backend | Until backend purge | **LBI** | No |
| D-14 | **Installed package list & versions** | `collect_system_info.py` | In-memory resource attributes | Logfire backend | Until backend purge | **LBI** | No |
| D-15 | **Failed export payloads (Protobuf)** | `DiskRetryer` on export failure | OS temp dir `/tmp/logfire-retryer-*/` | Logfire backend (on retry) | Until retry succeeds or process death | **MBI–HBI** | Yes — mirrors content of D-01 through D-10 |
| D-16 | **CLI activity log** | `logfire` CLI subcommands | `~/.logfire/log.txt` | None (local only) | Until manually deleted | **LBI** | No |
| D-17 | **Read tokens** | `logfire read-tokens create` | Application memory / env var | Logfire Query API | Until revoked | **HBI** | No |
| D-18 | **OTel baggage** | `logfire.get_context()` / inbound requests | In-memory span attributes | Logfire backend | Until backend purge | **MBI** | Potentially |

---

## Data Flow Summary

```
[End User Request]
        │
        ▼
[Host Application] ──── auto-instrumentation hooks ────►
        │
        ├── HTTP framework (FastAPI / Django / Flask)
        │     • URL, route, method, status code → span attrs
        │     • Request/response headers (if capture_headers=True) → span attrs
        │     • Request/response body (httpx only, if capture_all=True) → span attrs
        │
        ├── LLM provider (OpenAI / Anthropic)
        │     • Full request JSON (messages, model, parameters) → request_data attr
        │     • Full model response → response_data attr
        │     • *** SCRUBBING BYPASSED for logfire.openai / logfire.anthropic scopes ***
        │
        ├── Database (SQLAlchemy / asyncpg / psycopg)
        │     • SQL query text → db.statement attr (SAFE_KEY: never scrubbed)
        │     • Parameterized query params typically NOT captured
        │
        ├── Function calls (@instrument / auto_trace)
        │     • All function arguments → span attrs (scrubbed by key pattern)
        │
        └── Exceptions
              • Exception type, message, stacktrace → span attrs (SAFE_KEYs)
                (exception.message never scrubbed)
                       │
                       ▼
              [In-Memory BatchSpanProcessor]
                       │
                       ├── [Scrubbing Processor] ◄── pattern-match key/value names
                       │     • Redacts values under keys matching: password, secret, api_key,
                       │       session, cookie, auth*, credential, private_key, ssn, jwt, ...
                       │     • DOES NOT apply to: db.statement, http.url, url.query,
                       │       exception.message, gen_ai.*.messages, request_data/response_data
                       │       (OpenAI/Anthropic spans entirely skipped)
                       │
                       ▼
              [OTLP HTTP Exporter] ──HTTPS──► Logfire Backend
              (Authorization: Bearer LOGFIRE_TOKEN)
              │
              ├── On success: payload discarded from memory
              └── On failure: payload written to /tmp/logfire-retryer-*/
                              (raw Protobuf, no encryption, OS temp dir permissions)
                              ──► Daemon thread retries with exponential backoff
```

**Trust boundary crossings:**
- All telemetry crosses TB-1 to the Logfire SaaS platform (US: `logfire-us.pydantic.dev` / EU: `logfire-eu.pydantic.dev`) over HTTPS
- No other third-party services receive telemetry data from the SDK at runtime
- LiteLLM, DSPy, Google GenAI instrumentation uses third-party OTel instrumentation packages that export through the same pipeline

---

## Findings

Findings are ordered Critical → High → Medium → Low.

---

### [CRITICAL] — LLM Spans Bypass Scrubbing Entirely; No Content Opt-Out for OpenAI/Anthropic

- **SDL Phase**: Implementation / Design
- **File**: `logfire/_internal/scrubbing.py` (lines 199–205); `logfire/_internal/main.py` (lines 1224–1314, 1328–1425)
- **Category**: Data Collection / Data Transmission
- **Data Elements Affected**: D-01 (LLM prompt text), D-02 (LLM model responses), all personal data users may supply in chat messages
- **Description**:  
  The `Scrubber.scrub_span()` method contains an explicit early-return bypass for all spans from the `logfire.openai` and `logfire.anthropic` instrumentation scopes:

  ```python
  def scrub_span(self, span: ReadableSpanDict):
      scope = span['instrumentation_scope']
      if scope and scope.name in ['logfire.openai', 'logfire.anthropic']:
          return   # ← entire span skipped, no scrubbing
  ```

  This means that for every OpenAI chat completion or Anthropic message call:
  - The `request_data` attribute (version=1) contains the full JSON request body including all `messages` (system prompt, user messages, conversation history).
  - The `response_data` attribute contains the full model response text.
  - Under `version='latest'`, `gen_ai.input.messages` and `gen_ai.output.messages` contain structured copies of the same content.
  
  None of these are ever scrubbed. If a user's chat message says "My SSN is 123-45-6789" or includes a credit card number, that data is transmitted verbatim to the Logfire backend.

  Additionally, `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`, and `pydantic_ai.all_messages` are permanently in `SAFE_KEYS`, meaning even non-LLM spans that happen to set these attributes would bypass scrubbing for those keys.

  There is **no `capture_content=False` parameter** on `instrument_openai()` or `instrument_anthropic()`. The only way to prevent content capture is to not instrument at all or to use a custom `scrubbing.callback` — which requires detailed internal knowledge and still would not override the scope-level bypass.

  Contrast this with:
  - `instrument_google_genai()`: doc comment says content requires `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` (opt-in)
  - `instrument_pydantic_ai()`: has explicit `include_content: bool | None` parameter

- **Regulatory Reference**: GDPR Art. 5(1)(c) (data minimization); GDPR Art. 25 (privacy by design and by default); CCPA § 1798.100 (consumer right to disclosure of data collected)
- **Recommendation**:
  1. **Immediate**: Add a `capture_content: bool = True` parameter to `instrument_openai()` and `instrument_anthropic()`. When `False`, omit `request_data.messages`, `response_data.message`, `gen_ai.input.messages`, `gen_ai.output.messages` from the span.
  2. **Consider changing default to `capture_content=False`** to align with privacy-by-design (GDPR Art. 25). Users who need content for debugging can opt in.
  3. Remove the scope-level scrubbing bypass. Instead, protect only specific non-sensitive LLM metadata (token counts, model name, finish reason) via SAFE_KEYS and let the standard scrubber process message content.
  4. Add a note in `instrument_openai()` and `instrument_anthropic()` docstrings (as `instrument_google_genai()` does) about the privacy implications of capturing LLM content.

---

### [HIGH] — `db.statement` in SAFE_KEYS — SQL Queries Never Scrubbed

- **SDL Phase**: Design / Implementation
- **File**: `logfire/_internal/scrubbing.py` (line 138)
- **Category**: Data Storage / Data Transmission
- **Data Elements Affected**: D-03 (SQL query text)
- **Description**:  
  The string `'db.statement'` is listed in `BaseScrubber.SAFE_KEYS`, which causes the scrubber to pass SQL query text through to the backend completely unmodified. For properly parameterized queries, parameter values are typically not part of the statement text. However:
  - Developers who build SQL with string interpolation (e.g., for ORM raw queries, admin tooling) may include user-supplied values directly in the query text.
  - SQL errors or debug statements may echo back query values that contain PII.
  - Tools like SQLAlchemy's `literal_binds=True` rendering mode produce fully inlined SQL that appears in `db.statement`.
  
  The rationale for whitelisting `db.statement` is to prevent false-positive scrubbing of query syntax that contains SQL keywords like `SELECT … WHERE auth_token = ?`. However, this comes at the cost of allowing PII in the query text to be transmitted.

- **Regulatory Reference**: GDPR Art. 5(1)(c) (data minimization); general best practice for observability tooling
- **Recommendation**:
  1. Remove `'db.statement'` from SAFE_KEYS and instead add SQL keyword exemptions explicitly (e.g., allow `SELECT`, `INSERT`, `WHERE`, SQL operators) rather than blanket-allowing the entire value.
  2. Alternatively, provide a `scrub_sql` option in `ScrubbingOptions` that applies the scrubber to `db.statement` values.
  3. At minimum, add documentation warning developers that SQL query text is transmitted unredacted and advising use of parameterized queries.

---

### [HIGH] — HTTP URLs and Query Strings in SAFE_KEYS — Never Scrubbed

- **SDL Phase**: Design / Implementation
- **File**: `logfire/_internal/scrubbing.py` (lines 133–136, 145–146)
- **Category**: Data Transmission
- **Data Elements Affected**: D-04 (HTTP request URLs), D-05 (query strings)
- **Description**:  
  The following keys are in `SAFE_KEYS` and are never scrubbed:
  - `'http.url'`
  - `'http.target'`
  - `'url.full'`
  - `'url.path'`
  - `'url.query'`

  URLs frequently contain PII or sensitive data in query parameters, including:
  - Authentication tokens: `?token=eyJhbGc...`, `?api_key=sk-...`
  - Session identifiers: `?session_id=abc123`
  - User identifiers: `?user_id=12345`, `?email=user@example.com`
  - Search terms: `?q=John+Smith+ssn+123456789`

  These are transmitted verbatim to the Logfire backend for every instrumented HTTP request or outbound call. Note that `url.query` is in SAFE_KEYS — even if it directly contains a password or token, it will not be scrubbed.

- **Regulatory Reference**: GDPR Art. 5(1)(c) (data minimization); GDPR Art. 5(1)(f) (integrity and confidentiality)
- **Recommendation**:
  1. Remove `'url.query'` from SAFE_KEYS and apply pattern scrubbing to query parameters (parsing `key=value` pairs and redacting values under sensitive keys).
  2. For `'url.full'` and `'http.url'`, apply the scrubber to the query-string portion of the URL specifically.
  3. Document that full URLs (including query strings) are captured and transmitted.
  4. Consider redacting known-sensitive query parameter patterns (e.g., `token`, `api_key`, `password`, `session`) from URL values by default.

---

### [HIGH] — Exception Messages in SAFE_KEYS — User-Supplied Data Not Scrubbed

- **SDL Phase**: Design / Implementation
- **File**: `logfire/_internal/scrubbing.py` (lines 128–130)
- **Category**: Data Transmission
- **Data Elements Affected**: D-08 (exception messages)
- **Description**:  
  `'exception.message'`, `'exception.stacktrace'`, and `'exception.type'` are in `SAFE_KEYS` and are not processed by the scrubber. Exception messages frequently contain user-supplied input, for example:
  - Pydantic validation errors: `"value is not a valid email address: user@real-domain.com"`
  - HTTP 400 responses: `"Invalid input: user provided SSN 123-45-6789"`
  - Database constraint errors that echo values: `"duplicate key value violates unique constraint: (email)=(user@example.com)"`

  This data is transmitted verbatim to the Logfire backend.

  The rationale for protecting exception messages from scrubbing is likely to prevent breaking exception reporting. However, it means that user data present in exception messages is never protected.

- **Regulatory Reference**: GDPR Art. 5(1)(c) (data minimization)
- **Recommendation**:
  1. Remove `'exception.message'` from SAFE_KEYS or apply a targeted scrub that only checks for patterns within the value (not key-name matching).
  2. Consider replacing it with a configurable exception message scrubbing option in `ScrubbingOptions`.
  3. Apply value-level pattern scanning to `exception.message` to catch known PII patterns embedded in error text.

---

### [HIGH] — Unencrypted Telemetry Persisted to Disk in Retry Queue

- **SDL Phase**: Design / Implementation
- **File**: `logfire/_internal/exporters/otlp.py` (lines 105–217); `DiskRetryer`
- **Category**: Data Storage
- **Data Elements Affected**: D-15 (disk retry queue — mirrors D-01 through D-10)
- **Description**:  
  `DiskRetryer` writes failed OTLP export payloads (raw Protobuf bytes) to files in the OS temp directory under a `logfire-retryer-*` prefix (created via `mkdtemp()`). On POSIX systems, `mkdtemp()` creates the directory with mode `0700`, which provides OS-level access control. However:
  - Files in the directory are Protobuf-encoded OTLP spans that may contain LLM prompts, SQL queries, function arguments, HTTP body content, and all other personal data captured by the SDK — **without any encryption at rest**.
  - The files are not cleaned up on normal process exit (the daemon thread exits silently if it has not yet retried).
  - Up to 512 MB of telemetry data can accumulate.
  - On Windows or container environments with shared /tmp, directory permissions may be weaker than `0700`.
  - Backup tools, container image snapshots, or log collection agents running as root may capture these files.

- **Regulatory Reference**: GDPR Art. 5(1)(f) (integrity and confidentiality — "processed in a manner that ensures appropriate security"); GDPR Art. 32 (security of processing)
- **Recommendation**:
  1. Encrypt the Protobuf payload before writing to disk using a per-session ephemeral key (stored only in memory).
  2. Alternatively, provide a configuration option to disable disk retry entirely (`disk_retry: bool = False`).
  3. Implement a time-based retention limit (e.g., delete files older than 24 hours) in addition to the size limit.
  4. Add a cleanup routine that runs at normal process exit to delete retry files.
  5. Document the disk retry behavior, what data it stores, and how to disable it.

---

### [HIGH] — No Opt-Out for LLM Content Capture (OpenAI/Anthropic vs. Inconsistent Defaults)

- **SDL Phase**: Design / Requirements
- **File**: `logfire/_internal/main.py` (lines 1224–1314, 1328–1425, 1427–1441)
- **Category**: Data Collection
- **Data Elements Affected**: D-01, D-02
- **Description**:  
  There is a significant inconsistency in content-capture defaults across LLM integrations:

  | Integration | Content Captured by Default | Opt-Out Available |
  |---|---|---|
  | `instrument_openai()` | Yes (full messages in `request_data`) | No |
  | `instrument_anthropic()` | Yes (full messages in `request_data`) | No |
  | `instrument_pydantic_ai()` | Yes | Yes — `include_content=False` parameter |
  | `instrument_google_genai()` | **No** (requires `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`) | N/A (opt-in) |
  | `instrument_openai_agents()` | Yes | No |

  The OpenAI Responses API and Chat Completions API both capture full message content (including all user turns, system prompts, and tool call results) with no way to disable this short of not calling `instrument_openai()`.

  Many production applications capture user conversations through OpenAI/Anthropic and those conversations may contain names, addresses, health conditions, financial information, or other personal data. The lack of a content opt-out makes GDPR data minimization compliance very difficult.

- **Regulatory Reference**: GDPR Art. 25 (privacy by design and by default); GDPR Art. 5(1)(c) (data minimization)
- **Recommendation**:
  1. Add `capture_content: bool = True` to `instrument_openai()` and `instrument_anthropic()`.
  2. Consider defaulting to `False` for a privacy-by-default posture, consistent with Google GenAI's approach.
  3. Add env-var equivalents (`LOGFIRE_OPENAI_CAPTURE_CONTENT`, `LOGFIRE_ANTHROPIC_CAPTURE_CONTENT`) for deployment-level control.

---

### [HIGH] — HTTP Header Capture Exposes Authorization and Cookie Values

- **SDL Phase**: Design / Implementation
- **File**: `logfire/_internal/utils.py` (lines 383–387); `logfire/_internal/integrations/fastapi.py` (line 78); `logfire/_internal/integrations/httpx.py` (lines 479–487)
- **Category**: Data Collection
- **Data Elements Affected**: D-05 (HTTP headers including Authorization, Cookie, X-API-Key)
- **Description**:  
  When `capture_headers=True` is passed to `instrument_fastapi()`, `instrument_django()`, `instrument_flask()`, `instrument_starlette()`, `instrument_httpx()`, or similar, the `maybe_capture_server_headers()` function sets:
  ```python
  os.environ['OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST'] = '.*'
  os.environ['OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE'] = '.*'
  ```
  This captures **all** HTTP headers. While the scrubber's DEFAULT_PATTERNS cover:
  - `cookie` → would match `http.request.header.cookie` key ✓
  - `auth(?!ors?\b)` → matches `http.request.header.authorization` key ✓
  - `api[._ -]?key` → matches `http.request.header.x-api-key` key ✓

  Sensitive custom headers that do not match any pattern would not be scrubbed. Common examples include:
  - `X-Session-Token`, `X-User-Token`, `X-CSRF-Token` (csrftoken matches, but xsrf also in list)
  - `X-Forwarded-For` (may expose user IP addresses — IP addresses are personal data under GDPR)
  - Any custom auth/identity headers with non-standard naming

  Furthermore, setting these env vars is **global and persistent** for the process — `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST=.*` affects all OTel HTTP instrumentors for the remainder of the process lifetime.

- **Regulatory Reference**: GDPR Art. 4(1) (IP address is personal data); GDPR Art. 5(1)(c) (data minimization)
- **Recommendation**:
  1. Replace `.*` (capture all headers) with a configurable allowlist or denylist of header names.
  2. Add `X-Forwarded-For` and other IP-revealing headers to the DEFAULT_PATTERNS to ensure scrubbing when captured.
  3. Document which headers are captured when `capture_headers=True` and their privacy implications.
  4. Consider providing `capture_headers: list[str]` (specific headers only) instead of a boolean flag.

---

### [MEDIUM] — Auto-Tracing and `@instrument` Capture All Function Arguments by Default

- **SDL Phase**: Design / Requirements
- **File**: `logfire/_internal/main.py` (lines 601–693); `logfire/_internal/instrument.py`; `logfire/_internal/auto_trace/`
- **Category**: Data Collection
- **Data Elements Affected**: D-07 (function arguments and return values)
- **Description**:  
  Both `@logfire.instrument(extract_args=True)` (the default) and `install_auto_tracing()` capture all function call arguments as span attributes. This includes:
  - Passwords, tokens, and API keys passed as function parameters
  - User profile objects, form data, and model instances
  - Any PII passed to application business logic

  The scrubber applies pattern matching to attribute **key names** — so `def process_order(user_email, card_number, ...)` would pass `user_email` and `card_number` as keys. `card_number` does not match `credit[._ -]?card`, so it would not be scrubbed. `user_email` does not match any DEFAULT_PATTERNS, so it would not be scrubbed either.

  `install_auto_tracing()` in particular can affect entire modules, potentially capturing all parameters of every function in a module without explicit developer review. The Threat Model (Component 5) notes this is a significant information disclosure surface.

- **Regulatory Reference**: GDPR Art. 5(1)(c) (data minimization); GDPR Art. 25 (privacy by design)
- **Recommendation**:
  1. Consider changing the default of `extract_args` to `False` for `@logfire.instrument()` in a future major version.
  2. Add a documentation warning that all function arguments are captured.
  3. Add a section to `ScrubbingOptions` for "additional sensitive parameter names" to protect beyond DEFAULT_PATTERNS.
  4. For `install_auto_tracing()`, document the privacy implications explicitly and recommend careful module scoping.

---

### [MEDIUM] — Scrubber DEFAULT_PATTERNS Covers Key Names But Lacks Content-Pattern PII Detection

- **SDL Phase**: Implementation / Verification
- **File**: `logfire/_internal/scrubbing.py` (lines 35–60)
- **Category**: Data Transmission
- **Data Elements Affected**: D-01 through D-10
- **Description**:  
  The scrubber works by matching attribute **key names** (and full-string attribute values) against a set of regex patterns. DEFAULT_PATTERNS covers standard secret key names (`password`, `api_key`, `secret`, etc.) but has important gaps:

  1. **Email addresses**: No pattern matches keys like `email`, `user_email`, `contact_email`, `email_address` — all of which are common Pydantic model fields.
  2. **Phone numbers**: No pattern matches `phone`, `phone_number`, `mobile`, `cell`.
  3. **Personal names**: No pattern for `first_name`, `last_name`, `full_name`.
  4. **IP addresses**: No pattern; IP addresses are personal data under GDPR.
  5. **National IDs**: Only `ssn` is covered via the word-boundary pattern; no `national_id`, `tax_id`, `passport_number`, etc.
  6. **Credit card key names**: Only `credit[._ -]?card` is covered; `card_number`, `pan`, `cc_number` would not match.
  7. **Date of birth**: No pattern for `dob`, `date_of_birth`, `birth_date`.

  Additionally, the scrubber's value-content scanning (for string values) works by checking if the value string itself contains a pattern keyword — e.g., a string value `"password123"` matches `password` and the whole value is scrubbed. This means that benign values like `"The user authorized the transaction"` would be scrubbed because "auth" matches `auth(?!ors?\b)`.

- **Regulatory Reference**: GDPR Art. 5(1)(c) (data minimization); general privacy best practice
- **Recommendation**:
  1. Expand DEFAULT_PATTERNS to include: `email`, `phone`, `mobile`, `first[_\-\.]?name`, `last[_\-\.]?name`, `birth[_\-\.]?date`, `dob`, `ip[_\-\.]?address`.
  2. Document the full list of covered patterns in the public API reference.
  3. Consider adding content-pattern scanning for known PII formats (email regex `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b`, basic phone patterns) as an opt-in mode.
  4. Provide a curated "PII mode" for `ScrubbingOptions` that adds all common personal data key patterns.

---

### [MEDIUM] — Pydantic Instrumentation Captures Full Validation Input/Output

- **SDL Phase**: Design / Requirements
- **File**: `logfire/_internal/main.py` (lines 1021–1068); `logfire/integrations/pydantic.py`
- **Category**: Data Collection
- **Data Elements Affected**: D-09 (Pydantic model validation data)
- **Description**:  
  `logfire.instrument_pydantic(record='all')` (which is the default when calling `instrument_pydantic()` without arguments) records both the input data and the validated output for every Pydantic model validation. Pydantic models are commonly used to model user registration, profile updates, payment information, health records, and similar personal data.

  The scrubber processes these attributes, so fields with matching key names (e.g., `password`) would be redacted. However, fields with names not in DEFAULT_PATTERNS (e.g., `email_address`, `date_of_birth`, `phone_number`) would be transmitted in full. The default `record='off'` for the older `PydanticPlugin` is superseded by `instrument_pydantic()` which defaults to `record='all'`.

- **Regulatory Reference**: GDPR Art. 5(1)(c) (data minimization); GDPR Art. 25 (privacy by design)
- **Recommendation**:
  1. Default `record` to `'failure'` or `'metrics'` rather than `'all'` to minimize data exposure.
  2. Document the privacy implications of each `record` mode in the `instrument_pydantic()` docstring.
  3. Recommend adding model-specific field exclusions for personal data fields in the scrubbing configuration.

---

### [MEDIUM] — MCP Tool Call Arguments and Responses Captured Without Scrubbing Bypass

- **SDL Phase**: Implementation
- **File**: `logfire/_internal/integrations/mcp.py` (lines 38–57)
- **Category**: Data Collection
- **Data Elements Affected**: D-10 (MCP tool call arguments and responses)
- **Description**:  
  The MCP instrumentation captures the full `request` object (which includes tool call arguments) and the `response` (which includes tool results) as span attributes. Unlike OpenAI/Anthropic which have the scrubbing bypass, MCP spans go through normal scrubbing. However:
  - Tool call arguments are stored under the key `'request'` — this is NOT in SAFE_KEYS and would be processed by the scrubber
  - The scrubber would recurse into the request object, but would only redact fields with key names matching DEFAULT_PATTERNS
  - MCP tool responses (`'response'`) are similarly stored and scrubbed only by key-name matching
  - Tool arguments often contain user-supplied data passed directly from LLM function calls, which may include names, addresses, or other PII with non-sensitive-sounding key names

- **Regulatory Reference**: GDPR Art. 5(1)(c) (data minimization)
- **Recommendation**:
  1. Add a `capture_arguments: bool = True` parameter to `instrument_mcp()`.
  2. Add a `capture_responses: bool = True` parameter to `instrument_mcp()`.
  3. Document MCP tool argument capture in the integration documentation.

---

### [MEDIUM] — No Time-Based Retention Limit for Disk Retry Queue

- **SDL Phase**: Design
- **File**: `logfire/_internal/exporters/otlp.py` (lines 105–222)
- **Category**: Data Storage
- **Data Elements Affected**: D-15 (disk retry queue)
- **Description**:  
  The `DiskRetryer` has a 512 MB size limit (`MAX_TASK_SIZE`) but no time-based retention limit. If the Logfire backend is unreachable for an extended period, telemetry files containing personal data could persist in `/tmp/logfire-retryer-*/` indefinitely. The daemon thread exits when the process terminates — remaining files are **not cleaned up** and will persist in the temp directory. If the same process is restarted, a new `DiskRetryer` instance creates a **new temp directory** — the old files are permanently orphaned.

- **Regulatory Reference**: GDPR Art. 5(1)(e) (storage limitation); GDPR Art. 5(1)(f) (integrity and confidentiality)
- **Recommendation**:
  1. Add a max-age limit (e.g., configurable via `DiskRetryer(max_age_seconds=3600)`).
  2. At process startup, scan for and delete orphaned `logfire-retryer-*` directories older than the max-age.
  3. Add a cleanup hook via `atexit` or the `shutdown()` path to delete retry files when telemetry is no longer needed.

---

### [LOW] — Authentication Tokens Stored in Plaintext Files Without Permission Enforcement

- **SDL Phase**: Implementation
- **File**: `logfire/_internal/auth.py` (line 22–23); `logfire/_internal/config.py`
- **Category**: Data Storage
- **Data Elements Affected**: D-11 (write tokens), D-12 (user tokens)
- **Description**:  
  Both `~/.logfire/default.toml` (user OAuth tokens) and `.logfire/logfire_credentials.json` (project write tokens) are written in plaintext without setting restrictive file permissions (e.g., `chmod 0600`). On multi-user systems or misconfigured environments, these files could be readable by other users. The Threat Model (Component 2) confirms "no `chmod 600` applied to token file after write." The user token file stores `{token, expiration}` pairs — the token grants management-level API access.

- **Regulatory Reference**: GDPR Art. 32 (security of processing — appropriate technical measures); general security best practice
- **Recommendation**:
  1. After writing `~/.logfire/default.toml`, call `os.chmod(path, 0o600)` to restrict access.
  2. After writing `.logfire/logfire_credentials.json`, apply the same restriction.
  3. Document the file locations and advise developers to protect them in `.gitignore` (`.logfire/` directory already has a generated `.gitignore *` as noted in `ensure_data_dir_exists`).

---

### [LOW] — Privacy Documentation Does Not Disclose SDK-Level Data Collection to SDK Consumers

- **SDL Phase**: Requirements / Release
- **File**: `docs/compliance.md`; SDK documentation
- **Category**: Compliance
- **Data Elements Affected**: All (D-01 through D-18)
- **Description**:  
  `docs/compliance.md` contains three sentences noting SOC2 Type II, HIPAA, and GDPR compliance badges with links to the trust page. It provides no disclosure to **SDK users** (the developers who embed `logfire` in their applications) about:
  - What categories of data the SDK automatically captures from their end users
  - How to configure or disable specific data capture
  - Data retention periods on the Logfire backend
  - The existence of the disk retry queue and its data persistence behavior
  - How to configure scrubbing for their specific use case
  - Whether they need a Data Processing Agreement (DPA) with Pydantic

  This is inadequate for SDK users who are themselves data controllers under GDPR and need to understand what their SDK vendor captures to fulfill their own privacy obligations.

- **Regulatory Reference**: GDPR Art. 13–14 (right to be informed); GDPR Art. 28 (processor obligations)
- **Recommendation**:
  1. Create a dedicated **Privacy Guide** in the documentation covering: what data is captured per integration, how scrubbing works and its limitations, how to minimize data capture, and retention policies.
  2. Publish a **Data Processing Agreement (DPA)** template for SDK users who are GDPR-covered data controllers.
  3. Add a "Privacy" section to each integration's documentation page.
  4. Document the disk retry queue and how to disable it.

---

### [LOW] — No GDPR Legal Basis Documentation for Telemetry Processing

- **SDL Phase**: Requirements
- **File**: SDK documentation (general)
- **Category**: Compliance
- **Data Elements Affected**: All personal data elements
- **Description**:  
  The SDK transmits potentially personal data (end-user conversations, IP addresses extracted from URLs, exception messages with user input) to the Logfire backend. No documentation exists to help SDK users understand what legal basis (GDPR Art. 6) applies to this processing, or what purpose limitation applies. SDK users who are GDPR data controllers must have a lawful basis for this data flow and must include it in their privacy notices.

- **Regulatory Reference**: GDPR Art. 6 (lawfulness of processing); GDPR Art. 13 (information to be provided)
- **Recommendation**:
  1. Document the recommended legal basis for using Logfire telemetry (typically **Legitimate Interest** for operational telemetry, subject to LIA; or **Contract** for the direct service relationship).
  2. Provide guidance on what SDK users must disclose in their own privacy notices.
  3. Clarify in DPA terms whether Pydantic acts as a data processor or sub-processor.

---

### [LOW] — Inconsistent LLM Content Capture Defaults Across Integrations

- **SDL Phase**: Design
- **File**: `logfire/_internal/main.py` (lines 1224–1469)
- **Category**: Data Collection
- **Data Elements Affected**: D-01, D-02
- **Description**:  
  As noted in the Critical finding, the content-capture defaults across LLM integrations are inconsistent:
  - OpenAI, Anthropic, OpenAI Agents: **content ON by default, no opt-out**
  - Google GenAI: **content OFF by default, opt-in via env var**
  - PydanticAI: **content ON by default, opt-out via `include_content=False`**
  - LiteLLM, DSPy: delegate to their respective third-party instrumentation packages (behavior varies)

  This inconsistency makes it difficult for developers to reason about what is captured across a multi-provider LLM application.

- **Regulatory Reference**: GDPR Art. 5(1)(a) (transparency); GDPR Art. 25 (privacy by design)
- **Recommendation**:
  1. Standardize on a consistent `capture_content` parameter across all LLM integrations.
  2. Consider defaulting all LLM integrations to `capture_content=False` (like Google GenAI) for a privacy-by-default approach.
  3. Document the unified content capture policy in a single reference location.

---

### [LOW] — Package Version Fingerprinting via Resource Attributes

- **SDL Phase**: Design
- **File**: `logfire/_internal/collect_system_info.py`
- **Category**: Data Collection
- **Data Elements Affected**: D-14 (installed package names and versions)
- **Description**:  
  `collect_package_info()` uses `importlib.metadata.distributions()` to enumerate all installed Python packages and their versions. This full package list is transmitted as an OTLP resource attribute on every SDK initialization. While this is LBI data and has legitimate debugging uses, it reveals the complete technology stack of the application to the Logfire backend, which could aid in targeted attacks if the Logfire backend were compromised.

- **Regulatory Reference**: General security best practice
- **Recommendation**:
  1. Add a configuration flag to disable or limit package version collection (e.g., include only packages explicitly listed by the user).
  2. Alternatively, document that this data is collected and transmitted.

---

## Compliance Gap Analysis

### GDPR Compliance

| Requirement | Article | Status | Gap |
|---|---|---|---|
| Lawful basis for processing | Art. 6 | ⚠️ Partial | No documented legal basis guidance for SDK users; basis depends on their use case |
| Privacy notice accuracy | Art. 13–14 | ❌ Gap | SDK documentation does not disclose what end-user data is captured |
| Data minimization | Art. 5(1)(c) | ❌ Gap | LLM content, SQL queries, URLs, exception messages captured without minimization |
| Purpose limitation | Art. 5(1)(b) | ✅ Met | Telemetry is used for observability; no evidence of secondary use in SDK |
| Storage limitation | Art. 5(1)(e) | ⚠️ Partial | Backend retention is outside SDK scope; disk retry queue has no time-based limit |
| Integrity & confidentiality | Art. 5(1)(f) | ❌ Gap | Disk retry queue unencrypted; token files not permission-restricted |
| Privacy by design | Art. 25 | ❌ Gap | LLM content capture on by default; no `capture_content=False` default |
| Data Processing Agreements | Art. 28 | ⚠️ Unknown | No DPA template published for SDK users |
| Right to erasure | Art. 17 | ⚠️ Limited | Backend can delete projects; no SDK mechanism for per-user erasure |
| Right to access / portability | Art. 15, 20 | ⚠️ Limited | Query API exists for read token holders; no per-user data export |

### CCPA Compliance

| Requirement | Section | Status | Gap |
|---|---|---|---|
| Disclosure of data collected | §1798.100 | ❌ Gap | SDK documentation does not disclose categories of personal info collected |
| Right to deletion | §1798.105 | ⚠️ Limited | Backend-level project deletion available; no per-user deletion API in SDK |
| Do Not Sell mechanism | §1798.120 | ✅ N/A | No evidence of data selling; all data flows to Logfire backend under service contract |
| Consumer rights request | §1798.100–130 | ⚠️ Limited | No SDK-level mechanism; depends on backend implementation |

### General Privacy Hygiene

| Check | Status | Notes |
|---|---|---|
| PII in log files | ✅ Controlled | `~/.logfire/log.txt` is CLI activity log (LBI); not application PII |
| PII in error messages | ❌ Gap | `exception.message` in SAFE_KEYS; user data in exceptions transmitted |
| PII in URLs | ❌ Gap | `url.query`, `http.url` in SAFE_KEYS; not scrubbed |
| PII in cache keys | ✅ N/A | SDK does not use cache keys |
| Encryption in transit (TLS 1.2+) | ✅ Met | HTTPS via `requests` library; TLS certificate validation enabled by default |
| Encryption at rest (HBI/MBI) | ❌ Gap | Disk retry queue unencrypted; token files plaintext |
| Sensitive headers scrubbed | ✅ Mostly | `cookie`, `authorization`, `api_key` patterns cover most cases; custom headers may not be covered |
| Telemetry opt-in disclosure | ❌ Gap | No consent mechanism; SDK instruments silently on `logfire.configure()` |

---

## Third-Party Data Sharing

| Third Party | Data Shared | Purpose | Transmission Mechanism | Notes |
|---|---|---|---|---|
| **Logfire Platform (US)** `logfire-us.pydantic.dev` | All telemetry (D-01 through D-10) | Observability / tracing backend | OTLP/HTTP POST with write token, TLS | GCP `us-east4` region; primary data destination |
| **Logfire Platform (EU)** `logfire-eu.pydantic.dev` | All telemetry (D-01 through D-10) | Observability / tracing backend | OTLP/HTTP POST with write token, TLS | GCP `europe-west4` region; for EU data residency |
| **Logfire Management API** | User token, project metadata | CLI auth/project management | HTTPS | User token only; not telemetry |
| **Logfire Query API** | SQL query, read token | Telemetry query access | HTTPS | Read token only |
| **Logfire Variables API** | API key, OTel baggage | Remote config polling | HTTPS long-poll | Optional feature |
| **PyPI** | None | Package distribution | N/A | Package download only |

**Key findings on third-party sharing:**
- The SDK does **not** share telemetry with any third party other than the Logfire platform.
- LLM API providers (OpenAI, Anthropic, Google) receive data from the *host application*, but the Logfire SDK does not forward data to them — it only captures data flowing to/from them and sends it to Logfire.
- Third-party OTel instrumentation packages (openinference, opentelemetry-instrumentation-*) are used in-process and export through the same Logfire pipeline; they do not have their own network endpoints.
- No analytics, advertising, or error-tracking third parties receive data from the SDK.

---

## User Rights Assessment

| Right | GDPR Article | CCPA | SDK Support | Notes |
|---|---|---|---|---|
| Right to be informed | Art. 13–14 | §1798.100 | ❌ Gap | No disclosure documentation for SDK users to pass to their end users |
| Right of access | Art. 15 | §1798.110 | ⚠️ Partial | `LogfireQueryClient` with read token provides data access but not per-subject |
| Right to rectification | Art. 16 | — | ❌ Not Available | No mechanism to correct specific span attribute values |
| Right to erasure | Art. 17 | §1798.105 | ⚠️ Partial | Backend can delete entire projects; no per-user or per-trace deletion in SDK |
| Right to restrict processing | Art. 18 | — | ❌ Not Available | No per-user opt-out mechanism |
| Right to data portability | Art. 20 | §1798.100 | ⚠️ Partial | Arrow/JSON export via query API; not per-subject |
| Right to object | Art. 21 | §1798.120 | ❌ Not Available | No mechanism in SDK |

**Overall assessment**: The SDK provides limited support for data subject rights, primarily because telemetry data is not indexed by individual end-user identity. Fulfilling erasure or access requests for a specific individual would require backend-level search by user-identifying attributes (e.g., user ID in span attributes), which is outside the SDK scope but not facilitated by the SDK.

---

## Recommendations Summary

| Priority | Finding | Recommendation |
|---|---|---|
| **Critical** | LLM scrubber bypass | Add `capture_content=False` to OpenAI/Anthropic; remove scope bypass in scrubber |
| **High** | `db.statement` in SAFE_KEYS | Remove from SAFE_KEYS; apply scrubbing to SQL query text |
| **High** | URLs in SAFE_KEYS | Remove `url.query` from SAFE_KEYS; scrub query parameter values |
| **High** | `exception.message` in SAFE_KEYS | Apply value-level scrubbing to exception messages |
| **High** | Unencrypted disk retry queue | Encrypt payloads or provide disable option; add time-based retention |
| **High** | No LLM content opt-out | Standardize `capture_content` parameter; default to `False` |
| **High** | Header capture breadth | Use allowlist for `capture_headers`; add IP-revealing headers to patterns |
| **Medium** | Auto-trace PII surface | Default `extract_args=False`; document privacy implications |
| **Medium** | Scrubber pattern gaps | Add `email`, `phone`, `first_name`, `last_name`, `dob` to DEFAULT_PATTERNS |
| **Medium** | Pydantic instrumentation defaults | Default `record='failure'`; document privacy implications |
| **Medium** | MCP tool arguments | Add `capture_arguments=False` option |
| **Medium** | Disk retry retention | Add time-based limit; cleanup at process exit |
| **Low** | Token file permissions | Apply `chmod 0600` after writing token files |
| **Low** | Privacy documentation | Write a dedicated Privacy Guide; publish DPA template |
| **Low** | Legal basis documentation | Document recommended GDPR Art. 6 basis for SDK users |
| **Low** | Inconsistent LLM defaults | Standardize content capture API across all LLM integrations |
| **Low** | Package fingerprinting | Make package version collection configurable |

---

*Report generated by Privacy Audit Agent. This report covers the open-source SDK only; the closed-source Logfire platform backend is out of scope.*