---
name: microsoft-sdl
description: "Use when: reviewing code for security, performing threat modeling, classifying bugs by severity, applying SDL practices, discussing MSPP (Microsoft Security Privacy Platform) bug bar, CVE severity, CVSS scoring, SDL phases, security requirements, or security design review. Trigger phrases: SDL, MSPP, bug bar, threat model, security review, CVSS, CVE severity, security classification, privacy review."
---

# Microsoft SDL & MSPP Classification Knowledge

## Microsoft Security Development Lifecycle (SDL)

The SDL is a set of mandatory security practices applied to all software development. It maps to the standard dev lifecycle phases.

### SDL Phases

| Phase | Key Activities |
|-------|----------------|
| **Training** | Annual security/privacy training for all engineers |
| **Requirements** | Define security requirements; identify regulatory constraints; assess security/privacy risk |
| **Design** | Threat modeling (STRIDE); attack surface reduction; secure design review |
| **Implementation** | Use approved tools; ban unsafe functions; static analysis (e.g., CodeQL, ESLint security rules, Roslyn analyzers) |
| **Verification** | Dynamic analysis (fuzzing, DAST); penetration testing; final security review |
| **Release** | Incident response plan; final security review sign-off |
| **Response** | Security response process; patch SLAs tied to MSPP severity |

### Threat Modeling — STRIDE

Use STRIDE to categorize threats during design:

| Letter | Threat | Violated Property | Example |
|--------|--------|-------------------|---------|
| **S** | Spoofing | Authentication | Forging a user identity or session token |
| **T** | Tampering | Integrity | Modifying data in transit or at rest |
| **R** | Repudiation | Non-repudiation | Denying an action occurred without audit trail |
| **I** | Information Disclosure | Confidentiality | Leaking credentials, PII, or internal data |
| **D** | Denial of Service | Availability | Exhausting resources via crafted input |
| **E** | Elevation of Privilege | Authorization | Gaining admin/system access without authorization |

### Attack Surface Reduction

- Remove unused features, APIs, and endpoints
- Disable functionality by default; require explicit enablement
- Limit the code that runs with elevated trust
- Prefer allow-lists over deny-lists

### Banned Functions / Risky Patterns

Adapt to the project's language and framework. Common examples by context:

#### Web / JavaScript / TypeScript

| Risky Pattern | Safer Alternative |
|---------------|-------------------|
| `innerHTML = userInput` | `textContent` or DOM APIs |
| `eval(str)`, `new Function(str)` | Structured parsing; `JSON.parse` for data |
| `dangerouslySetInnerHTML` | Avoid; sanitize with DOMPurify if unavoidable |
| Storing secrets in `localStorage` / `sessionStorage` | Use HttpOnly cookies or server-side session |
| `document.write()` | Modern DOM insertion |
| Trusting `postMessage` without origin check | Validate `event.origin` explicitly |

#### Python

| Risky Pattern | Safer Alternative |
|---------------|-------------------|
| `eval()` / `exec()` on untrusted input | Structured parsing; `ast.literal_eval` for literals |
| `pickle.loads()` on untrusted data | Use JSON or a safe serialization format |
| `os.system()` / `subprocess.call(shell=True)` | `subprocess.run()` with argument list (no shell) |
| SQL string concatenation | Parameterized queries / ORM |
| `yaml.load()` without `Loader` | `yaml.safe_load()` |
| Hardcoded secrets in source | Environment variables, secret manager, or config vault |

#### C# / .NET

| Risky Pattern | Safer Alternative |
|---------------|-------------------|
| String concatenation in SQL | Parameterized queries / EF Core |
| `Process.Start()` with user input | Validate and sanitize arguments; avoid shell execution |
| Deserializing untrusted data (`BinaryFormatter`) | Use `System.Text.Json` or safe serializers |
| Hardcoded connection strings with secrets | Use `Secret Manager`, Azure Key Vault, or env vars |
| Disabling certificate validation | Use proper TLS certificate chain validation |

#### Java / Kotlin

| Risky Pattern | Safer Alternative |
|---------------|-------------------|
| `Runtime.getRuntime().exec()` with user input | Use `ProcessBuilder` with validated arguments |
| `ObjectInputStream.readObject()` on untrusted data | Use JSON or validated deserialization with type filtering |
| SQL string concatenation in JDBC | Use `PreparedStatement` with parameterized queries |
| Hardcoded secrets in source | Use environment variables or secret vault |

#### Go

| Risky Pattern | Safer Alternative |
|---------------|-------------------|
| `os/exec.Command` with unsanitized input | Validate and sanitize all arguments |
| `text/template` for HTML output | Use `html/template` for auto-escaping |
| SQL string concatenation | Use parameterized queries (`$1`, `?`) |

#### Rust

| Risky Pattern | Safer Alternative |
|---------------|-------------------|
| `unsafe` blocks without justification | Minimize unsafe; document invariants |
| `Command::new()` with user input | Validate arguments; avoid shell execution |
| SQL string formatting | Use parameterized queries via sqlx or diesel |

---

## MSPP Bug Bar — Security Severity Classifications

The MSPP Bug Bar defines the **minimum fix SLA** and **severity** for security vulnerabilities based on worst-case impact assuming default configuration.

### Severity Levels

#### Critical
- Remote, unauthenticated code execution (RCE) without user interaction
- Widespread data loss or system compromise
- **Fix SLA**: ASAP / emergency patch

#### Important (High)
- RCE requiring user interaction
- Elevation of Privilege from low to high integrity
- Significant information disclosure (credentials, PII)
- Denial of Service (permanent / highly reliable)
- **Fix SLA**: Next update cycle (typically 30–90 days)

#### Moderate (Medium)
- Spoofing with limited impact
- Tampering with non-sensitive data
- Information disclosure of non-sensitive data
- DoS (temporary or requires specific conditions)
- XSS in low-privilege context
- **Fix SLA**: Discretionary; may be deferred to major release

#### Low
- Requires significant user interaction or unlikely preconditions
- Defense-in-depth bypass with no direct impact
- Minor information disclosure (e.g., software version)
- **Fix SLA**: Best effort; tracked but lower priority

---

## CVSS v3.1 Quick Reference

| Score | Rating |
|-------|--------|
| 9.0–10.0 | Critical |
| 7.0–8.9 | High |
| 4.0–6.9 | Medium |
| 0.1–3.9 | Low |
| 0.0 | None |

### Key CVSS Metrics

- **Attack Vector (AV)**: Network / Adjacent / Local / Physical
- **Attack Complexity (AC)**: Low / High
- **Privileges Required (PR)**: None / Low / High
- **User Interaction (UI)**: None / Required
- **Scope (S)**: Unchanged / Changed
- **Confidentiality / Integrity / Availability Impact**: None / Low / High

---

## Privacy Classifications

### Data Sensitivity Tiers (SDL Privacy)

| Tier | Description | Examples |
|------|-------------|---------|
| **High Business Impact (HBI)** | Personal data, credentials, financial data | Passwords, PII, payment info |
| **Medium Business Impact (MBI)** | Pseudonymous or aggregated data | Pseudonymized user IDs, analytics |
| **Low Business Impact (LBI)** | Non-personal, public data | Anonymous scores, config values |

### Privacy SDL Requirements

- Collect only minimum necessary data (data minimization)
- Document data flows in threat model
- Obtain consent before collecting personal data
- Provide deletion/export mechanisms for personal data (GDPR Article 17/20)
- Encrypt HBI data in transit (TLS 1.2+) and at rest

---

## Applying SDL to a Project

### Step 1 — Identify the Attack Surface

For each project, enumerate:
- **Entry points**: APIs, CLI arguments, file inputs, network listeners, user-facing forms, message queues
- **Data stores**: Databases, file systems, caches, cloud storage, client-side storage
- **External integrations**: Third-party APIs, package registries, CI/CD pipelines, cloud services
- **Authentication/authorization boundaries**: Who can access what, and how identity is verified
- **Deployment context**: Public internet, internal network, desktop app, embedded system

### Step 2 — Map Threats with STRIDE

Apply STRIDE per component. For each component ask:
- Can an attacker **Spoof** an identity or source?
- Can data be **Tampered** with in transit or at rest?
- Can actions occur without an audit trail (**Repudiation**)?
- Can sensitive data be **disclosed** to unauthorized parties?
- Can the component be made unavailable (**Denial of Service**)?
- Can an attacker **Elevate Privilege** beyond their authorization?

### Step 3 — Scan for Banned Patterns

Search the codebase for risky patterns appropriate to the project's language(s).

### Step 4 — Review Dependencies

Audit all direct and transitive dependencies for known CVEs, lockfile integrity, version pinning, and dependency confusion.

### Step 5 — Classify and Prioritize Findings

Use severity levels and CVSS scoring to classify each finding. Prioritize by severity and exploitability.

### SDL Checklist for New Features

- [ ] Threat model updated for new data flows
- [ ] No new banned functions or risky patterns introduced
- [ ] Input from user/external sources validated before use
- [ ] No secrets hardcoded in source or client-side storage
- [ ] New dependencies reviewed for known CVEs
- [ ] Security headers and transport security not weakened
- [ ] Logging and monitoring covers new functionality
- [ ] Privacy impact assessed for any new data collection

---

## Quick Severity Decision Tree

```
Is the bug exploitable remotely without authentication?
├── Yes, with no user interaction → CRITICAL
├── Yes, but requires user interaction → HIGH
└── No remote exploitation
    ├── Local EoP to system/admin → HIGH
    ├── Sensitive data disclosure → HIGH or MEDIUM (based on sensitivity)
    ├── DoS (reliable) → HIGH; (unreliable) → MEDIUM
    └── Limited/theoretical impact → LOW
```
