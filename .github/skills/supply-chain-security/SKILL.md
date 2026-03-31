---
name: supply-chain-security
description: "Use when: auditing dependencies, reviewing supply chain risks, running vulnerability scans on packages, checking lockfile hygiene, evaluating dependency pinning, assessing SLSA levels, or checking for dependency confusion attacks. Trigger phrases: supply chain, dependency audit, lockfile, package pinning, SLSA, dependency confusion, third-party packages, transitive dependencies."
---

# Supply Chain Security

Supply chain attacks target the dependencies your code pulls in rather than your code itself. This skill covers how to assess, audit, and harden the dependency supply chain for any project, regardless of package ecosystem.

---

## Step 1 — Inventory Dependencies

| Ecosystem | Manifest | Lockfile | Audit Command |
|-----------|----------|----------|---------------|
| **npm / Node.js** | `package.json` | `package-lock.json` / `yarn.lock` / `pnpm-lock.yaml` | `npm audit` |
| **Python / pip** | `requirements.txt` / `pyproject.toml` / `Pipfile` | `Pipfile.lock` / `poetry.lock` | `pip audit` / `safety check` |
| **Java / Maven** | `pom.xml` | (resolved via `.m2/repository`) | `mvn dependency:tree` + OWASP plugin |
| **Java / Gradle** | `build.gradle` / `build.gradle.kts` | `gradle.lockfile` | `gradle dependencies` + OWASP plugin |
| **.NET / NuGet** | `*.csproj` / `packages.config` | `packages.lock.json` | `dotnet list package --vulnerable` |
| **Rust / Cargo** | `Cargo.toml` | `Cargo.lock` | `cargo audit` |
| **Go** | `go.mod` | `go.sum` | `govulncheck ./...` |
| **Ruby / Bundler** | `Gemfile` | `Gemfile.lock` | `bundle audit` |
| **PHP / Composer** | `composer.json` | `composer.lock` | `composer audit` |

### Dependency Categories

| Category | Risk Level |
|----------|------------|
| Runtime / production | **High** — runs in production |
| Build / dev | **Medium** — runs in CI |
| Install hooks | **High** — run arbitrary code at install time |

### Red Flags

- Install hooks (`postinstall`, `setup.py cmdclass`, `extensions`)
- Typosquatting candidates (names similar to popular packages)
- VCS / URL references bypassing registry integrity
- Unpinned / wildcard versions
- Recently transferred ownership

---

## Step 2 — Lockfile Audit

| Check | Concern |
|-------|--------|
| Present and committed | Missing = non-deterministic installs |
| Matches manifest | Drift = manual edits or merge conflicts |
| Integrity hashes | Should have checksums |
| Official registry URLs | No unknown mirrors |
| No local/VCS entries | Bypass registry integrity |
| Freshness | Stale lockfiles accumulate vulnerabilities |

---

## Step 3 — Run Vulnerability Audit

### Severity Mapping

| Audit Severity | MSPP Equivalent | Action |
|----------------|-----------------|--------|
| critical | Critical | Fix immediately; block deploy |
| high | High | Fix in current cycle |
| moderate | Medium | Fix in next release |
| low | Low | Assess and schedule |

---

## Step 4 — Dependency Confusion

- Are internal package names registered on the public registry?
- Can an attacker publish a malicious package with an internal name?
- Is registry configuration enforcing private resolution?

### Mitigations by Ecosystem

- **npm**: Scoped packages (`@org/`), `.npmrc` registry overrides
- **Python**: Single private index with PyPI proxying
- **.NET**: `NuGet.Config` with `<clear />` and source mapping
- **Go**: `GOPROXY` configuration for private modules
- **Java**: Repository mirrors in `settings.xml`

---

## Step 5 — SLSA Levels

| Level | Requirements | Prevents |
|-------|-------------|----------|
| **SLSA 1** | Documented build process | Accidental modifications |
| **SLSA 2** | Version controlled + hosted CI | Unauthorized builds |
| **SLSA 3** | Hardened build, non-falsifiable provenance | Compromised build system |
| **SLSA 4** | Two-person review, hermetic builds | Insider threats |

---

## Step 6 — High-Risk Package Categories

| Category | Why Risky |
|----------|-----------|
| Build plugins | Execute code at build time |
| Install hooks / native extensions | Run at install regardless of usage |
| Obfuscated source | Hard to audit |
| Recently transferred ownership | New maintainer may be malicious |
| Abandoned (>2 years) | Unpatched CVEs |
| Sensitive operations (auth, crypto, DB, HTTP) | Higher blast radius |

---

## Hardening Checklist

### Lockfile & Pinning
- [ ] Lockfile present, committed, up to date
- [ ] Integrity hashes verified
- [ ] Critical deps pinned to exact versions
- [ ] No VCS/local path refs in production deps

### Vulnerability Management
- [ ] Audit passes with zero critical/high findings
- [ ] Dependabot or Renovate configured
- [ ] Major version upgrades reviewed manually

### Build Integrity
- [ ] No unnecessary install hooks
- [ ] Build plugins audited
- [ ] CI uses hosted, version-controlled environment (SLSA 2+)

### Secrets & Registry
- [ ] Registry auth tokens in CI secrets, not committed
- [ ] Private registry enforced for internal packages

### Monitoring
- [ ] Automated CVE monitoring enabled
- [ ] Process for responding to critical CVEs within 48 hours
