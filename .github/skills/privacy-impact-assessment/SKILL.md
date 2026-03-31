---
name: privacy-impact-assessment
description: "Use when: performing a privacy impact assessment, PIA, DPIA, identifying personal data, classifying data sensitivity, reviewing GDPR compliance, CCPA compliance, data minimization, consent requirements, data retention, right to deletion, or privacy by design. Trigger phrases: privacy impact assessment, PIA, DPIA, GDPR, CCPA, personal data, data minimization, consent, right to deletion, data retention, privacy review, data inventory."
---

# Privacy Impact Assessment (PIA) Methodology

A Privacy Impact Assessment identifies what personal data a system collects, how it flows, what risks exist, and what controls are needed. This skill applies the Microsoft SDL privacy framework alongside GDPR/CCPA principles.

---

## When a PIA is Required (Microsoft SDL)

A PIA is mandatory when a new feature or system:
- Collects, stores, or processes PII
- Introduces new data flows across trust boundaries
- Changes the purpose of existing data use
- Integrates with third-party services that receive user data
- Uses persistent identifiers (user IDs, device IDs, cookies)

---

## Step 1 — Data Inventory

| Data Element | Where Collected | Where Stored | Who Can Access | Retention | Sensitivity |
|-------------|-----------------|-------------|----------------|-----------|-------------|

### Sensitivity Tiers

| Tier | Description | Examples |
|------|-------------|---------|
| **HBI** | Direct identifiers, credentials, financial, health data | Name, email, password, credit card, SSN, location |
| **MBI** | Pseudonymous identifiers, aggregated behavioral data | User IDs, session tokens, analytics, device fingerprints |
| **LBI** | Non-personal, public, fully anonymized data | Anonymous scores, public config |

---

## Step 2 — Data Flow Mapping

```
Collection → Processing → Storage → Transmission → Deletion
```

Note: trust boundary crossings, encryption status, third-party recipients.

---

## Step 3 — Legal Basis (GDPR Article 6)

| Legal Basis | When It Applies |
|-------------|-----------------|
| **Consent** | User explicitly opts in; must be withdrawable |
| **Contract** | Necessary to deliver the service |
| **Legitimate Interest** | Business need that doesn't override user rights |
| **Legal Obligation** | Required by law |

---

## Step 4 — Privacy Principles Checklist

- [ ] **Data Minimization** — only collect what's necessary
- [ ] **Purpose Limitation** — data not reused for undisclosed purposes
- [ ] **Storage Limitation** — retention periods defined; deletion mechanism exists
- [ ] **Accuracy** — users can correct inaccurate data
- [ ] **Integrity & Confidentiality** — HBI/MBI encrypted in transit and at rest
- [ ] **Privacy by Design** — default settings are most privacy-protective

---

## Step 5 — User Rights Assessment

| Right | GDPR Article | CCPA Section | Fulfillable? | How |
|-------|-------------|-------------|--------------|-----|
| Right to be informed | Art. 13-14 | §1798.100 | ? | Privacy notice |
| Right of access | Art. 15 | §1798.110 | ? | Data export |
| Right to rectification | Art. 16 | — | ? | Edit capability |
| Right to erasure | Art. 17 | §1798.105 | ? | Delete account/data |
| Right to restrict processing | Art. 18 | — | ? | Opt-out mechanism |
| Right to data portability | Art. 20 | §1798.100 | ? | Machine-readable export |
| Right to object | Art. 21 | §1798.120 | ? | Opt-out of data sale |

---

## Step 6 — Third-Party Data Sharing

| Third Party | Data Shared | Purpose | Legal Mechanism | DPA in Place? |
|------------|-------------|---------|-----------------|---------------|

Common categories: cloud providers, auth providers, analytics/telemetry, error reporting, payment processors, email/messaging, AI/ML services.

---

## Step 7 — Risk Register

```
### [SEVERITY] — Risk Title
- **Data Involved**: <element>
- **Likelihood**: Low / Medium / High
- **Impact**: Low / Medium / High
- **Description**: what could go wrong
- **Mitigation**: specific control
- **Owner**: who is responsible
```

### Severity Calibration

| Scenario | Severity |
|----------|----------|
| HBI data exposed (credentials, PII) | Critical / High |
| MBI data exposed | High / Medium |
| LBI data exposed | Medium / Low |
| Failure to honor deletion request | High (regulatory) |
| Missing consent for tracking | High (regulatory) |

---

## Privacy Hardening Quick Wins

- [ ] Remove/anonymize unnecessary data collection
- [ ] Never log PII to application logs or error reporting
- [ ] Encrypt HBI at rest; enforce TLS 1.2+ in transit
- [ ] Set `SameSite=Strict; Secure; HttpOnly` on cookies (web apps)
- [ ] Restrictive file permissions on config with user data (CLI/desktop)
- [ ] Document retention periods for each data store
- [ ] Implement data deletion mechanism
- [ ] Make telemetry opt-in with clear disclosure
- [ ] Never use PII as cache keys, DB keys, queue IDs, or in URLs
