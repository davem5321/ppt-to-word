---
name: threat-model
description: "Use when: creating a threat model, building a data flow diagram, identifying trust boundaries, enumerating entry points, running STRIDE analysis per component, or producing a THREAT_MODEL.md artifact. Trigger phrases: threat model, create threat model, data flow diagram, DFD, trust boundaries, entry points, STRIDE per component, threat modeling process."
---

# Threat Modeling Methodology

This skill defines the step-by-step process for producing a structured threat model document. It complements the `microsoft-sdl` skill (which covers STRIDE definitions and MSPP severity) by providing the *process* — how to discover assets, draw data flows, identify trust boundaries, and enumerate threats systematically.

---

## Step 1 — Define Scope & Objectives

- **System under review**: name, version, brief description
- **In scope**: components, data stores, interfaces being modelled
- **Out of scope**: explicitly list excluded areas
- **Security objectives**: what properties must the system protect?
- **Assumptions**: things treated as given

---

## Step 2 — Identify Assets

| Asset | Description | Sensitivity (HBI/MBI/LBI) | Owner |
|-------|-------------|--------------------------|-------|

Common categories: user data, application data, system resources, code/IP, secrets/keys, audit trails.

---

## Step 3 — Draw the Data Flow Diagram (DFD)

### DFD Elements

| Symbol | Meaning | Notation |
|--------|---------|----------|
| Rectangle | External entity | `[Entity]` |
| Circle/Oval | Process | `(Process)` |
| Open rectangle | Data store | `=Store=` |
| Arrow | Data flow | `→` |
| Dashed line | Trust boundary | `- - - - -` |

### Trust Boundary Rules

| Boundary | Examples |
|----------|----------|
| Client ↔ Network | Browser ↔ API server; desktop app ↔ cloud service |
| User input ↔ Application | CLI arguments, form data, file uploads |
| Application ↔ Data store | App ↔ database, file system, cache |
| Application ↔ Third-party | Outbound API calls, OAuth providers, AI/ML APIs |
| Public ↔ Internal network | Load balancer ↔ internal services |
| Privileged ↔ Unprivileged | Admin functions ↔ regular user functions |
| Build/CI ↔ Production | Pipeline ↔ deployment targets |

Mark every data flow that **crosses a trust boundary**.

---

## Step 4 — Enumerate Entry Points

| # | Entry Point | Data Type | Trust Level | Notes |
|---|-------------|-----------|-------------|-------|

Common categories: user input (UI), CLI arguments, HTTP requests, file system reads, database reads, third-party API responses, message queues, environment variables, imported packages, IPC.

---

## Step 5 — STRIDE Analysis Per Component

For each component on or crossing a trust boundary:

```
Component: <name>
Trust Boundary: <boundary>

| Threat | Applicable? | Scenario | Mitigation |
|--------|-------------|----------|------------|
| S – Spoofing | Yes/No/N/A | ... | ... |
| T – Tampering | Yes/No/N/A | ... | ... |
| R – Repudiation | Yes/No/N/A | ... | ... |
| I – Info Disclosure | Yes/No/N/A | ... | ... |
| D – Denial of Service | Yes/No/N/A | ... | ... |
| E – Elevation of Privilege | Yes/No/N/A | ... | ... |
```

---

## Step 6 — Rate & Prioritize Threats

### DREAD (lightweight scoring, 1–3 per factor)

| Factor | Question |
|--------|----------|
| **D**amage | How bad is the impact? |
| **R**eproducibility | How easy to reproduce? |
| **E**xploitability | How easy to exploit? |
| **A**ffected Users | How many impacted? |
| **D**iscoverability | How easy to find? |

### Severity Mapping

| DREAD Avg | Severity |
|-----------|----------|
| 2.5–3.0 | Critical / High |
| 1.5–2.4 | Medium |
| 1.0–1.4 | Low |

---

## Step 7 — Define Mitigations

For each threat: mitigation type (Prevent/Detect/Respond), specific control, owner, status (Open/In Progress/Mitigated/Accepted Risk).

---

## THREAT_MODEL.md Output Template

```markdown
# Threat Model — <Project Name>

**Date**: YYYY-MM-DD
**Version**: 1.0
**Scope**: <brief scope statement>
**Author**: <name or agent>

## 1. Scope & Objectives
## 2. Assets
## 3. Data Flow Diagram
## 4. Entry Points
## 5. Threat Analysis (STRIDE)
## 6. Threat Register
| ID | Component | STRIDE | Scenario | DREAD | Severity | Mitigation | Status |
## 7. Mitigations Summary
## 8. Out of Scope
```

---

## Quality Checklist

- [ ] All trust boundaries identified and labelled on DFD
- [ ] Every entry point enumerated
- [ ] STRIDE applied to every component on a trust boundary
- [ ] Every threat rated and assigned an owner
- [ ] No threats left as "TBD" without justification
- [ ] Mitigations are specific and actionable
- [ ] Out-of-scope items documented
