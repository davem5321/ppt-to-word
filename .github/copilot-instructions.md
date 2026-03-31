# Copilot Instructions

<skills>
<skill>
<name>microsoft-sdl</name>
<description>Use when: reviewing code for security, performing threat modeling, classifying bugs by severity, applying SDL practices, discussing MSPP bug bar, CVE severity, CVSS scoring, SDL phases, security requirements, or security design review. Trigger phrases: SDL, MSPP, bug bar, threat model, security review, CVSS, CVE severity, security classification, privacy review.</description>
<file>.github/skills/microsoft-sdl/SKILL.md</file>
</skill>
<skill>
<name>threat-model</name>
<description>Use when: creating a threat model, building a data flow diagram, identifying trust boundaries, enumerating entry points, running STRIDE analysis per component, or producing a THREAT_MODEL.md artifact. Trigger phrases: threat model, create threat model, data flow diagram, DFD, trust boundaries, entry points, STRIDE per component, threat modeling process.</description>
<file>.github/skills/threat-model/SKILL.md</file>
</skill>
<skill>
<name>supply-chain-security</name>
<description>Use when: auditing dependencies, reviewing supply chain risks, running vulnerability scans on packages, checking lockfile hygiene, evaluating dependency pinning, assessing SLSA levels, or checking for dependency confusion attacks. Trigger phrases: supply chain, dependency audit, lockfile, package pinning, SLSA, dependency confusion, third-party packages, transitive dependencies.</description>
<file>.github/skills/supply-chain-security/SKILL.md</file>
</skill>
<skill>
<name>privacy-impact-assessment</name>
<description>Use when: performing a privacy impact assessment, PIA, DPIA, identifying personal data, classifying data sensitivity, reviewing GDPR compliance, CCPA compliance, data minimization, consent requirements, data retention, right to deletion, or privacy by design. Trigger phrases: privacy impact assessment, PIA, DPIA, GDPR, CCPA, personal data, data minimization, consent, right to deletion, data retention, privacy review, data inventory.</description>
<file>.github/skills/privacy-impact-assessment/SKILL.md</file>
</skill>
</skills>

## Audit Preferences
When asked to audit, run ALL audit dimensions (security, privacy, accessibility, digital safety, supply-chain) in parallel and deliver a unified report. All findings must include SDL phase mapping and severity classification aligned with the Microsoft Security Development Lifecycle.

## Architecture Discovery
Before running any audit agents, the **ArchitectureDiscovery** agent must run first to produce `audit/ARCHITECTURE.md`. All downstream audit agents consume this shared context document instead of independently discovering the codebase.

## Report Dates
When a report requires a date or timestamp, use the current date provided in the conversation context (e.g., `The current date is ...`). Never fabricate or guess a date.
