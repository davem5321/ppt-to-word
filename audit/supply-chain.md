# Supply Chain Security Audit — Logfire Python SDK

**Date**: 2025-07-14  
**Auditor**: Supply Chain Security Agent (SDL-aligned)  
**Project**: `logfire` v4.31.0 + `logfire-api` v4.31.0  
**Repository**: `https://github.com/pydantic/logfire`  
**Ecosystem**: Python (uv workspace) + JavaScript (Pyodide test harness, not distributed)  
**Scope**: Dependency pinning, lockfile hygiene, install hooks, dependency confusion, transitive dependencies, GitHub Actions CI/CD security, PyPI release security, SLSA posture  
**Methodology**: Microsoft SDL — Implementation-phase (dependency selection) and Verification-phase (vulnerability scanning)

---

## Executive Summary

The Logfire Python SDK has a **strong foundational supply chain posture**: it uses `uv` with a committed lockfile (`uv.lock`) containing SHA256 integrity hashes for all packages, an `exclude-newer` freshness window that prevents newly published packages from being pulled in automatically, and OIDC Trusted Publisher authentication to PyPI for releases. Both `logfire` and `logfire-api` are registered on PyPI under the Pydantic organization, eliminating dependency confusion risk for those package names.

The **most significant risks** are in the CI/CD pipeline: no GitHub Actions are pinned to immutable commit SHAs, two critical actions (`pypa/gh-action-pypi-publish` and `re-actors/alls-green`) use **branch references** that can change at any time, and the Claude AI workflow grants write permissions to the repository and id-token to any user who types `@claude` in a GitHub comment. Additionally, the docs CI step bypasses the lockfile (`--upgrade`) while pulling from a private registry, and no artifact provenance (SLSA) attestations or SBOM are generated.

| Overall Risk Level | Finding Count |
|---|---|
| 🔴 High | 3 |
| 🟠 Medium | 7 |
| 🟡 Low | 5 |
| **Total** | **15** |

---

## Phase 1 — Ecosystem Discovery

| Ecosystem | Manifest | Lockfile | Hash-verified |
|---|---|---|---|
| Python (`logfire`) | `pyproject.toml` | `uv.lock` ✅ committed | ✅ SHA256 per artifact |
| Python (`logfire-api`) | `logfire-api/pyproject.toml` | Shared `uv.lock` | ✅ SHA256 per artifact |
| JavaScript (Pyodide test only, **not distributed**) | `pyodide_test/package.json` | `pyodide_test/package-lock.json` ✅ | ✅ via npm lockfile |

---

## Phase 2 — Dependency Inventory

### 2.1 Runtime Dependencies (`logfire`)

| Package | Version Specifier | Purpose | Pinning Quality |
|---|---|---|---|
| `opentelemetry-sdk` | `>=1.39.0, <1.40.0` | OTel traces/metrics/logs SDK | ✅ Narrow minor range |
| `opentelemetry-exporter-otlp-proto-http` | `>=1.39.0, <1.40.0` | OTLP/HTTP Protobuf exporter | ✅ Narrow minor range |
| `opentelemetry-instrumentation` | `>=0.41b0` | Base instrumentation framework | ⚠️ Lower bound only |
| `rich` | `>=13.4.2` | Terminal output / console exporter | ⚠️ Lower bound only |
| `protobuf` | `>=4.23.4` | OTLP protobuf serialisation | ⚠️ Lower bound only (older floor) |
| `typing-extensions` | `>=4.1.0` | Typing backports | ⚠️ Lower bound only |
| `tomli` | `>=2.0.1; python_version < '3.11'` | TOML config parsing | ⚠️ Lower bound only |
| `executing` | `>=2.0.1` | Frame/AST inspection for f-string magic | ⚠️ Lower bound only |

**Assessment**: Runtime deps use lower-bound constraints in the manifest, which is standard PyPI practice for libraries that need to avoid over-constraining downstream consumers. All are resolved to exact locked versions with SHA256 hashes in `uv.lock`, which provides the actual integrity guarantee.

### 2.2 Notable Optional Dependencies

| Package | Version Specifier | Risk Note |
|---|---|---|
| `openinference-instrumentation-litellm` | `>= 0` | No floor — any version accepted |
| `openinference-instrumentation-dspy` | `>= 0` | No floor — any version accepted |
| `httpx` | `>=0.27.2` | HTTP client; auth/network sensitive |
| `pydantic` | `>=2` | Broad lower bound |

### 2.3 Dev/Build Dependencies — Notable Entries

| Package | Version Specifier | Risk |
|---|---|---|
| `hatchling` | *(none — `requires = ["hatchling"]` in `[build-system]`)* | 🔴 Build tool completely unpinned |
| `pydantic-docs` | `{ git = "https://github.com/pydantic/pydantic-docs/" }` | 🔴 Git ref, **no commit SHA** |
| `langgraph` | `>= 0` | No floor |
| `surrealdb` | `>= 0` | No floor |
| `google-genai` | `>= 0` | No floor |
| `claude-agent-sdk` | `>= 0` | New/emerging package, no floor |
| `pip` | `>= 0` | Including `pip` itself with no floor |
| `cryptography` | `>= 44.0.0` | Security-sensitive, but has reasonable floor |

**Note**: All dev deps with `>= 0` or loose bounds are **resolved and locked** in `uv.lock` with SHA256 hashes, substantially mitigating the risk for reproducible developer installs.

### 2.4 Install Hooks (Python)

No Python `postinstall` hooks or `setup.py cmdclass` patterns were found in the `logfire` or `logfire-api` packages themselves. However, several **transitive dependencies include C extensions** compiled at install time:

- `aiohttp` — C extension (Cython), compiles from source on unsupported platforms
- `protobuf` — Ships pre-compiled wheels; source build fallback uses C extension  
- `cffi` — C FFI library; required by `cryptography`
- `pydantic-core` (via `pydantic`) — Rust extension compiled via maturin

These compile-from-source paths execute arbitrary build scripts (`setup.py`, `build.rs`) at install time on platforms without pre-built wheels. This is standard practice but represents code execution during installation.

---

## Phase 3 — Lockfile Health

| Check | Status | Notes |
|---|---|---|
| Lockfile present | ✅ | `uv.lock` committed to the repository |
| Covers all direct + transitive deps | ✅ | uv resolves full dependency graph |
| Integrity hashes present | ✅ | SHA256 for every sdist and wheel artifact |
| Registry URLs official | ✅ | All `source = { registry = "https://pypi.org/simple" }` |
| No local path entries (runtime) | ✅ | `logfire-api` is a workspace member (expected) |
| No VCS entries in lockfile | ✅ | pydantic-docs VCS ref is docs-only and not in uv.lock resolved packages (docs only install) |
| `exclude-newer` freshness window | ✅ | Locked at `2026-03-20T18:22:31.273676Z` — prevents packages released after that date |
| `exclude-newer-span = "P1W"` | ✅ | Requires packages be at least 1 week old before inclusion |
| Lockfile used in CI | ✅ | `uv sync --frozen` in lint/test jobs |
| Lockfile bypassed in docs build | ⚠️ | `uv pip install --upgrade` in docs job — see Finding M-03 |
| Private registry packages bypass freshness | ⚠️ | `mkdocs-material` and `mkdocstrings-python` have `exclude-newer = false` |

**Lockfile Verdict**: Healthy for reproducible developer and test installs. The docs CI step is the only location where lockfile integrity is bypassed.

---

## Phase 4 — Findings

---

### [HIGH] H-01 — GitHub Actions Branch-Pinned: Release Gate and Gatekeeper

- **SDL Phase**: Verification / Release  
- **Category**: CI/CD Security — Unpinned Action Reference  
- **File/Location**: `.github/workflows/main.yml` lines 152, 189, 223  
- **Affected Actions**:  
  - `pypa/gh-action-pypi-publish@release/v1` — **branch reference** (line 223, release job)  
  - `re-actors/alls-green@release/v1` — **branch reference** (line 189, branch-protection gate)  
- **Description**:  
  Both of these actions are referenced by a **mutable branch name** (`release/v1`), not an immutable commit SHA. An attacker who gains write access to either the `pypa` or `re-actors` GitHub organisation can push malicious code to those branches, which will be executed in the next CI run without any change visible in this repository's history. The `gh-action-pypi-publish` action is the **direct publisher of logfire to PyPI**, meaning a compromised action here could push a backdoored package to all users. The `alls-green` action is the **branch-protection gate** — a compromised version could mark all jobs as passing regardless of outcome, allowing malicious PRs to merge.
- **CVE**: N/A (architectural risk)
- **CVSS Analogy**: ~8.1 (High) — network-exploitable, no user interaction required once attacker controls upstream branch
- **Recommendation**:  
  1. Pin **all** actions to their full commit SHA. Use a tool like [Ratchet](https://github.com/sethvargo/ratchet) or [pin-github-action](https://github.com/mheap/pin-github-action) to automate this.  
  2. Add the human-readable tag as a comment for maintainability:  
     ```yaml
     # pypa/gh-action-pypi-publish@release/v1
     uses: pypa/gh-action-pypi-publish@67339c736fd9354cd4f8cb0b744f2b82a74b5c70
     ```
  3. Repeat for every action reference in all workflow files.

---

### [HIGH] H-02 — Claude AI Workflow: Write Permissions Granted to External Trigger

- **SDL Phase**: Design / Implementation  
- **Category**: CI/CD Security — Excessive Permissions  
- **File/Location**: `.github/workflows/claude.yml`  
- **Description**:  
  The Claude AI workflow (`anthropics/claude-code-action@v1`) grants `contents: write`, `pull-requests: write`, `issues: write`, and `id-token: write` permissions. It is **triggered by any GitHub user** who mentions `@claude` in a comment on any issue or pull request — including users with no collaborator access. The action also uses `actions/checkout@v5` pinned to a mutable tag.  
  
  This creates the following attack vectors:  
  - Any external user can trigger the action by opening an issue with `@claude` in the title/body.  
  - The action is instructed to use Claude with `--max-turns 30`, granting the AI agent broad ability to make commits (`contents: write`), modify PRs, and obtain OIDC tokens (`id-token: write`).  
  - A crafted prompt in an issue (prompt injection) could instruct Claude to make malicious code changes, disclose secrets visible in the workflow environment, or take other unauthorised actions.  
  - `id-token: write` in combination with `contents: write` is an elevated permission combination — if the action can request OIDC tokens, it could potentially authenticate to external services (e.g., cloud providers if configured).
- **CVE**: N/A  
- **Recommendation**:  
  1. **Restrict triggering**: Gate the workflow on `github.event.sender.login` being in an allow-list of maintainers, or check for a specific label that only maintainers can apply.  
  2. **Remove `id-token: write`** unless there is a specific documented need for OIDC in the Claude workflow.  
  3. **Implement prompt injection defences**: Instruct Claude (via `system-prompt`) not to execute commands based on user-supplied content from issue bodies.  
  4. **Pin the action to a commit SHA**: `anthropics/claude-code-action@v1` → pin to SHA.  
  5. Consider using `permissions: {}` (deny all) as the default at the job level and explicitly grant only what is needed.

---

### [HIGH] H-03 — All GitHub Actions Unpinned to Commit SHAs (Tag-Only)

- **SDL Phase**: Verification  
- **Category**: CI/CD Security — Unpinned Action References  
- **File/Location**: All workflow files  
- **Affected Actions** (beyond H-01):  

  | Action | Ref Used | File |
  |---|---|---|
  | `actions/checkout` | `@v4`, `@v5`, `@v6` (tag) | All workflows |
  | `astral-sh/setup-uv` | `@v7` (tag) | `main.yml`, `weekly_deps_test.yml`, `copilot-setup-steps.yml` |
  | `actions/upload-artifact` | `@v4` (tag) | `main.yml` |
  | `actions/download-artifact` | `@v4` (tag) | `main.yml` |
  | `codecov/codecov-action` | `@v4` (tag) | `main.yml` |
  | `codecov/test-results-action` | `@v1` (tag) | `main.yml` |
  | `actions/setup-node` | `@v4` (tag) | `main.yml` |
  | `actions/setup-python` | `@v5` (tag) | `check_changelog.yml` |
  | `samuelcolvin/check-python-version` | `@v4.1` (tag) | `main.yml` |
  | `slackapi/slack-github-action` | `@v2.0.0` (tag) | `weekly_deps_test.yml` |
  | `anthropics/claude-code-action` | `@v1` (tag) | `claude.yml` |

  Also note: **inconsistent versions** of `actions/checkout` across files (`@v4`, `@v5`, `@v6`), suggesting workflows drift.

- **Description**:  
  Git tags are mutable by default. While GitHub allows tag immutability settings, tag references do not provide the same cryptographic guarantee as commit SHA references. A compromised third-party action maintainer account could force-push to a tag, causing all downstream users to silently run malicious code. This risk applies to all non-first-party GitHub Actions listed above.  
  
  Of particular concern:  
  - `codecov/codecov-action`: The Codecov supply chain attack (April 2021) demonstrated how a malicious CI action can exfiltrate CI secrets, including `ANTHROPIC_API_KEY`, `ALGOLIA_WRITE_API_KEY`, `SLACK_WEBHOOK_URL`, `UV_EXTRA_INDEX_URL`, and the OIDC token used for PyPI publishing.  
  - `astral-sh/setup-uv`: This action installs the `uv` package manager itself, which subsequently resolves and installs all project dependencies. A compromised version could tamper with the uv binary or modify dependency resolution.
- **Recommendation**:  
  Pin every action reference to an immutable commit SHA. Standardise on `actions/checkout@v6` (or the latest) across all workflows. Set up Dependabot for GitHub Actions to automate SHA updates:  
  ```yaml
  # .github/dependabot.yml
  version: 2
  updates:
    - package-ecosystem: "github-actions"
      directory: "/"
      schedule:
        interval: "weekly"
  ```

---

### [MEDIUM] M-01 — Build Backend (`hatchling`) Completely Unpinned

- **SDL Phase**: Implementation  
- **Category**: Unpinned Version / Build Tool  
- **File/Location**: `pyproject.toml` line 2  
- **Description**:  
  The `[build-system]` section declares `requires = ["hatchling"]` with **no version constraint**. The build backend is the first code that executes when building the package — it is executed before any dependency resolution or lockfile checks. An unpinned build backend means that any version of hatchling (including a hypothetically compromised future release) could be used.  
  
  `hatchling` runs `setup`/`build` hooks and has full access to the source tree and environment during the build process. While `uv.lock` does pin the version of `hatchling` used in the development environment, the `requires = [...]` field is read separately during `pip install logfire` from source (e.g., in `pip install .` scenarios) and does not use the lockfile.
- **Recommendation**:  
  Pin hatchling to a compatible range: `requires = ["hatchling>=1.26,<2"]` (adjust based on current version in lockfile). Add hatchling to the lockfile's `exclude-newer` tracking.

---

### [MEDIUM] M-02 — `pydantic-docs` VCS Dependency Without Commit SHA

- **SDL Phase**: Implementation  
- **Category**: Unpinned Version / VCS Reference  
- **File/Location**: `pyproject.toml` lines 221–222 (`[tool.uv.sources]`)  
- **Description**:  
  ```toml
  pydantic-docs = { git = "https://github.com/pydantic/pydantic-docs/" }
  ```  
  This docs dependency is fetched directly from GitHub **without specifying a commit SHA or tag**. Every `uv sync` will fetch the latest HEAD commit of that repository. The `pydantic-docs` repository is under the Pydantic organisation, reducing (but not eliminating) the risk. However:  
  - If the repository is compromised (e.g., a maintainer account takeover), the malicious commit is immediately pulled into the docs CI.  
  - The docs CI runs with `ALGOLIA_WRITE_API_KEY` in the environment — a malicious docs dependency could exfiltrate this secret.  
  - `allow-direct-references = true` in `[tool.hatch.metadata]` is required to support this pattern and also enables arbitrary URL/VCS dependencies in other contexts.
- **Recommendation**:  
  Pin to a specific commit SHA:  
  ```toml
  pydantic-docs = { git = "https://github.com/pydantic/pydantic-docs/", rev = "abc123def456..." }
  ```  
  Or publish `pydantic-docs` to PyPI and reference it as a normal dependency.

---

### [MEDIUM] M-03 — Docs Build Bypasses Lockfile via `--upgrade` + Private Registry

- **SDL Phase**: Verification  
- **Category**: Lockfile Issue / Supply Chain  
- **File/Location**: `.github/workflows/main.yml` lines 46–48  
- **Description**:  
  The docs job runs:  
  ```bash
  uv pip install --upgrade mkdocs-material 'mkdocstrings-python<2.0.3' 'mkdocstrings<1' griffe==0.48.0
  ```  
  with `UV_EXTRA_INDEX_URL: ${{ secrets.UV_EXTRA_INDEX_URL }}` pointing to a private PyPI registry.  
  
  This step:  
  1. **Bypasses the `uv.lock` lockfile** entirely with `--upgrade`, making the docs build non-reproducible.  
  2. Installs from a **private registry** whose contents are not versioned in the repository.  
  3. `mkdocs-material` and `mkdocstrings-python` have `exclude-newer = false` in the lockfile options, meaning the normal 1-week freshness window is **disabled** for these packages.  
  4. If the private registry URL is leaked (e.g., via a CI log), attackers could probe it.  
  5. If the private registry is compromised, malicious versions could be installed in CI and potentially exfiltrate `ALGOLIA_WRITE_API_KEY`.  
  
  Note: The docs build CI does not publish production artifacts, so the blast radius is limited to secrets in the docs workflow environment.
- **Recommendation**:  
  1. Add `mkdocs-material`, `mkdocstrings-python`, `mkdocstrings`, and `griffe` to the public PyPI lock in `uv.lock` using the public versions.  
  2. If proprietary versions are required from the private registry, document why and implement a separate, clearly-scoped docs build step that treats these as explicitly trusted but acknowledges the bypass.  
  3. Replace `--upgrade` with a pinned install (`uv sync --frozen --group docs`) if possible.

---

### [MEDIUM] M-04 — No SLSA Provenance Attestations or Artifact Signing

- **SDL Phase**: Release  
- **Category**: SLSA Assessment / Provenance  
- **File/Location**: `.github/workflows/main.yml` (release job)  
- **Description**:  
  The current release pipeline achieves approximately **SLSA Level 2**:  
  
  | SLSA Requirement | Status |
  |---|---|
  | L1: Documented build process | ✅ (GitHub Actions workflow) |
  | L1: Build is scripted | ✅ |
  | L2: Version controlled source | ✅ |
  | L2: Hosted build service | ✅ (GitHub Actions) |
  | L2: Authenticated build | ✅ (OIDC Trusted Publisher to PyPI) |
  | L3: Non-falsifiable provenance | ❌ (no `slsa-github-generator`) |
  | L3: Isolated build environment | ❌ (not hermetic) |
  | L3: Provenance signed and attached to artifact | ❌ |
  | L3: SBOM generation | ❌ |
  
  Without SLSA L3 provenance, there is no cryptographic proof that a given PyPI artifact was built from a specific commit. Users cannot verify that the published package was not tampered with between the build and publication.
- **Recommendation**:  
  1. Add [slsa-github-generator](https://github.com/slsa-framework/slsa-github-generator) to the release workflow to generate L3 provenance:  
     ```yaml
     - uses: slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v1
     ```  
  2. Enable PyPI's Trusted Publisher provenance verification (partially done via OIDC, but enhance with artifact attestations).  
  3. Generate an SBOM as part of the release:  
     ```bash
     uv pip list --format=freeze | pip-licenses --format=markdown > sbom.md
     # Or use cyclonedx-bom:
     cyclonedx-py environment > sbom.json
     ```

---

### [MEDIUM] M-05 — Weekly CI Installs Pydantic from Git Without SHA

- **SDL Phase**: Verification  
- **Category**: VCS Reference Without Pinning  
- **File/Location**: `.github/workflows/weekly_deps_test.yml` lines 75, 71  
- **Description**:  
  ```yaml
  - run: uv pip install git+https://github.com/pydantic/pydantic.git
  - run: uv sync --python ${{ matrix.python-version }} --upgrade
  ```  
  The weekly deps test intentionally pulls the latest `pydantic` from GitHub HEAD and runs `uv sync --upgrade` to test against bleeding-edge dependency versions. This is a deliberate testing strategy.  
  
  However, this weekly job runs on GitHub's standard infrastructure with access to the `SLACK_WEBHOOK_URL` secret. If a malicious commit lands on `pydantic/pydantic` `main` branch (e.g., via a compromised contributor), the weekly test would execute that code in this repository's CI context with access to the Slack webhook.  
  
  Additionally, `uv sync --upgrade` will pull any newly published packages (subject to the 1-week window), which could include versions with newly introduced vulnerabilities.
- **Recommendation**:  
  1. Accept this as an intentional design decision with documented risk (testing against HEAD is valuable).  
  2. Consider running the weekly test in a **separate GitHub Environment** with no secrets attached, or with an explicitly scoped environment that only has access to the Slack webhook.  
  3. Enable GitHub's dependency review for scheduled workflows.

---

### [MEDIUM] M-06 — No Automated Dependency Vulnerability Scanning (Dependabot/Renovate)

- **SDL Phase**: Verification  
- **Category**: Vulnerability Management / Stale Package  
- **File/Location**: No `.github/dependabot.yml` present  
- **Description**:  
  No automated dependency update tool (Dependabot or Renovate) is configured. The project relies on manual lockfile updates (`uv sync --upgrade`) and the weekly CI job for detecting new dependency versions. This means:  
  - No automated alerts when a CVE is published against a locked dependency version.  
  - Security patches may not be applied until a manual update cycle.  
  - GitHub Actions versions are never automatically updated (see H-01, H-03).  
  
  The `exclude-newer-span = "P1W"` policy in `uv.lock` provides some protection against very new/potentially malicious packages, but does not alert when existing locked versions receive CVE disclosures.
- **Recommendation**:  
  1. Create `.github/dependabot.yml` to enable Dependabot for both pip and GitHub Actions:  
     ```yaml
     version: 2
     updates:
       - package-ecosystem: "pip"
         directory: "/"
         schedule:
           interval: "weekly"
         open-pull-requests-limit: 10
       - package-ecosystem: "github-actions"
         directory: "/"
         schedule:
           interval: "weekly"
     ```  
  2. Add `pip audit` (or `uv run pip-audit`) to the CI lint/check job to catch known CVEs in locked versions:  
     ```yaml
     - run: uv run pip-audit --require-hashes -r requirements.txt
     ```

---

### [MEDIUM] M-07 — `openinference` Optional Dependencies Effectively Unbounded

- **SDL Phase**: Implementation  
- **Category**: Unpinned Version  
- **File/Location**: `pyproject.toml` lines 84–85  
- **Description**:  
  ```toml
  litellm = ["openinference-instrumentation-litellm >= 0"]
  dspy = ["openinference-instrumentation-dspy >= 0"]
  ```  
  These optional runtime dependencies (installed when users do `pip install logfire[litellm]` or `pip install logfire[dspy]`) have **no lower bound at all** (`>= 0`). This means any future version of these packages — including a hypothetically malicious one — would be accepted without any version floor.  
  
  `openinference-instrumentation-*` packages are developed by Arize AI (an observability startup). They wrap LLM SDKs and have access to LLM prompt/response data flowing through the instrumented application. A compromised version could exfiltrate this sensitive data.
- **Recommendation**:  
  Research the current stable release of each package and add appropriate lower bounds:  
  ```toml
  litellm = ["openinference-instrumentation-litellm >= 0.30.0"]
  dspy = ["openinference-instrumentation-dspy >= 0.30.0"]
  ```  
  Monitor Arize AI's package releases and ownership changes.

---

### [LOW] L-01 — No SBOM Generated in Release Pipeline

- **SDL Phase**: Release  
- **Category**: SLSA Assessment / SBOM  
- **File/Location**: `.github/workflows/main.yml` (release job)  
- **Description**:  
  No Software Bill of Materials (SBOM) is generated or attached to PyPI releases or GitHub Releases. An SBOM would allow downstream consumers to identify all transitive dependencies included in the package and respond to CVEs affecting those components without needing to manually reconstruct the dependency graph.
- **Recommendation**:  
  Add SBOM generation to the release job:  
  ```bash
  # CycloneDX format (recommended):
  pip install cyclonedx-bom
  cyclonedx-py environment --of JSON -o sbom-cyclonedx.json
  
  # Or SPDX format:
  pip install spdx-tools
  ```  
  Attach the SBOM as a GitHub Release asset and/or publish alongside the PyPI wheel.

---

### [LOW] L-02 — Third-Party CI Runners (Depot) Used for Maintainer PRs

- **SDL Phase**: Verification  
- **Category**: CI/CD Security  
- **File/Location**: `.github/workflows/main.yml` lines 63–72  
- **Description**:  
  Maintainer PRs run on `depot-ubuntu-24.04-4` (Depot hosted runners) rather than standard GitHub-hosted runners. Depot is a third-party CI infrastructure provider. While Depot is a reputable vendor, using third-party runners means:  
  - CI secrets (`ANTHROPIC_API_KEY`, `ALGOLIA_WRITE_API_KEY`, `UV_EXTRA_INDEX_URL`, etc.) are accessible within Depot-hosted VMs.  
  - The build environment is partially outside GitHub's security controls.  
  - Fork PRs with the `ci:fast` label can also be routed to Depot runners.
- **Recommendation**:  
  1. Ensure Depot runner environments are explicitly scoped — never run release jobs (which have `id-token: write`) on Depot runners.  
  2. Verify Depot's security certifications and compliance posture.  
  3. Consider whether `ci:fast` label can be applied by external contributors — if so, gate Depot runner usage more strictly.

---

### [LOW] L-03 — `allow-direct-references = true` Enables Arbitrary VCS/URL Dependencies

- **SDL Phase**: Implementation  
- **Category**: Lockfile Issue / Supply Chain  
- **File/Location**: `pyproject.toml` line 237; `logfire-api/pyproject.toml` line 28  
- **Description**:  
  ```toml
  [tool.hatch.metadata]
  allow-direct-references = true
  ```  
  This setting (in both `logfire` and `logfire-api`) allows hatchling to accept direct URL/VCS references in dependencies. It is currently used by `pydantic-docs` (docs only). However, it also means that any contributor could inadvertently (or maliciously) add a direct GitHub URL or other VCS reference to the dependencies, bypassing PyPI registry integrity checks without triggering an obvious lint warning.
- **Recommendation**:  
  If `pydantic-docs` is moved to a proper PyPI package, remove `allow-direct-references = true` to re-enable stricter dependency hygiene enforcement.

---

### [LOW] L-04 — `protobuf` Lower Bound May Include Vulnerable Versions

- **SDL Phase**: Verification  
- **Category**: Known Vulnerability (Potential)  
- **Package**: `protobuf >= 4.23.4`  
- **File/Location**: `pyproject.toml` line 54  
- **Description**:  
  The `protobuf` runtime dependency has a lower bound of `4.23.4`, which predates **CVE-2024-7254** (Python/Ruby protobuf ReDoS via message parsing, CVSS 7.5 HIGH, patched in `4.25.4` and `5.x`). While `uv.lock` pins protobuf to a specific version that may already be patched, the manifest's lower bound means that `pip install logfire` without `uv.lock` (e.g., by a downstream user) could install a vulnerable version.  
  
  Additionally, the broad lower bound on `protobuf` encompasses the `4.x` major version line across a wide range of patch releases with varying CVE histories.
- **CVE**: CVE-2024-7254 (CVSS 7.5 HIGH) — may affect protobuf < 4.25.4 / 5.26.1  
- **Recommendation**:  
  1. Raise the lower bound: `protobuf >= 4.25.4` (or the latest patched version).  
  2. Run `pip audit` (or `uv run pip-audit`) against the locked environment to confirm the currently-pinned version is unaffected.

---

### [LOW] L-05 — `opentelemetry-instrumentation` Broad Lower Bound with Beta Anchor

- **SDL Phase**: Implementation  
- **Category**: Unpinned Version  
- **Package**: `opentelemetry-instrumentation >= 0.41b0`  
- **File/Location**: `pyproject.toml` line 52  
- **Description**:  
  The `opentelemetry-instrumentation` base package and all optional instrumentation packages use a lower bound anchored to a beta release (`0.41b0` or `0.42b0`). These packages provide monkey-patching hooks for popular frameworks (FastAPI, Django, SQLAlchemy, etc.) and execute code at instrumentation install time. A major regression or supply chain compromise in any of these packages could instrument applications with malicious tracing logic.  
  
  The locked version in `uv.lock` is a recent release, so active risk is low. The concern is the broad manifest range which could accept older vulnerable versions when the lockfile is not used.
- **Recommendation**:  
  Tighten optional dep lower bounds to match the current locked minor version series (e.g., `>= 0.55b0` for the current `0.55b0` release line).

---

## Phase 5 — Dependency Confusion Assessment

| Package | PyPI Registered | Owner | Risk |
|---|---|---|---|
| `logfire` | ✅ Yes | Pydantic (pydantic.dev) | None — project owns the name |
| `logfire-api` | ✅ Yes | Pydantic (pydantic.dev) | None — published alongside `logfire` in every release |
| All `opentelemetry-*` deps | ✅ Yes | OpenTelemetry (CNCF) | None — established project |
| `openinference-instrumentation-*` | ✅ Yes | Arize AI | Low — monitor ownership changes |
| `claude-agent-sdk` | ✅ Yes | Anthropic | Low — verify ownership, no version floor |
| `pydantic-docs` | ❌ Not on PyPI | Pydantic (private) | Low — docs only, internal repo |

**Key strength**: Both `logfire` and `logfire-api` are published to PyPI as part of the release workflow (`uv build --all` then `pypa/gh-action-pypi-publish`), ensuring no namespace vacancy for an attacker to register a malicious package under these names.

**`pydantic-docs`** is not on PyPI and is fetched from GitHub. If someone registered `pydantic-docs` on PyPI, it could potentially be picked up in certain install scenarios. This is limited to docs builds and does not affect the distributed SDK.

**No scoping** (e.g., `pydantic-org/logfire`) is used, which is acceptable since both package names are already registered and the namespace is controlled.

---

## Phase 6 — SLSA Assessment

| SLSA Level | Status | Evidence |
|---|---|---|
| **Level 1** — Scripted build | ✅ Achieved | `uv build --all` in `main.yml` release job |
| **Level 2** — Version controlled + hosted CI | ✅ Achieved | GitHub Actions on `refs/tags/**`; OIDC Trusted Publisher |
| **Level 3** — Non-falsifiable provenance + isolated build | ❌ Not achieved | No `slsa-github-generator`; no hermetic build; no artifact attestation |
| **Level 4** — Two-person review + hermetic builds | ❌ Not achieved | N/A for most projects at this stage |

**Current SLSA Level: 2**

**Positive signals**:
- OIDC Trusted Publisher configured for PyPI (`id-token: write` in release job + `environment: release`)
- Release is gated on tag creation + passing all CI checks
- `uv.lock` provides hermetic dependency resolution for builds
- `exclude-newer-span = "P1W"` freshness window adds time-based protection

**Gaps to reach SLSA 3**:
1. Add `slsa-framework/slsa-github-generator` to release workflow
2. Pin all actions to commit SHAs (prerequisite for SLSA 3)
3. Ensure the build environment is hermetic (no network access during build step)
4. Generate and publish SBOM

---

## Phase 7 — PyPI Release Security Assessment

| Control | Status | Notes |
|---|---|---|
| OIDC Trusted Publisher (no API token) | ✅ | `id-token: write` + `environment: release` |
| Release gated on CI passing | ✅ | `needs: [check]` in release job |
| Release gated on tag format | ✅ | `startsWith(github.ref, 'refs/tags/')` |
| Version/tag consistency check | ✅ | `samuelcolvin/check-python-version@v4.1` |
| Protected `release` environment | ✅ | `environment: release` (requires environment protection rules) |
| Both packages published atomically | ✅ | `uv build --all` builds both `logfire` and `logfire-api` |
| Artifact signing (sigstore/cosign) | ❌ | Not implemented |
| 2FA enforcement on PyPI accounts | ⚠️ | Assumed but not verifiable from this repo |
| `skip-existing: true` in publish action | ⚠️ | Suppresses errors if a version already exists — could hide accidental duplicate publishes |

**`skip-existing: true` caution**: While this prevents workflow failures on re-runs, it can silently succeed when a version was already published by a different (possibly malicious) process. Consider removing this or adding explicit alerting when the "skipped existing" condition is triggered.

---

## Dependency Risk Register

| Package | Version (Locked) | Risk Score | Top Risk Factor | Recommended Action |
|---|---|---|---|---|
| `pypa/gh-action-pypi-publish` | `release/v1` (branch) | **High** | Mutable branch ref in release critical path | Pin to commit SHA immediately |
| `re-actors/alls-green` | `release/v1` (branch) | **High** | Mutable branch ref; controls branch protection gate | Pin to commit SHA immediately |
| `anthropics/claude-code-action` | `v1` (tag) | **High** | Write perms + public trigger + tag (not SHA) | Restrict trigger; pin SHA |
| `hatchling` | Unpinned in `[build-system]` | **Medium** | No version bound on build backend | Add version range |
| `pydantic-docs` | Git HEAD (no SHA) | **Medium** | VCS dep without commit lock | Pin to commit SHA |
| `openinference-instrumentation-litellm` | `>= 0` (manifest) | **Medium** | No version floor; third-party; LLM data access | Add floor version |
| `openinference-instrumentation-dspy` | `>= 0` (manifest) | **Medium** | No version floor; third-party; LLM data access | Add floor version |
| `protobuf` | `>= 4.23.4` (manifest) | **Medium** | Lower bound includes CVE-2024-7254 range | Raise floor to >= 4.25.4 |
| `opentelemetry-sdk` | `>=1.39.0, <1.40.0` | **Low** | Range allows any 1.39.x patch; OTLP transport security | Monitor OTel security advisories |
| `opentelemetry-exporter-otlp-proto-http` | `>=1.39.0, <1.40.0` | **Low** | Same as above; handles token-bearing export | Monitor OTel security advisories |
| `rich` | `>=13.4.2` | **Low** | Terminal output only; lower bound only | Acceptable; lockfile mitigates |
| `executing` | `>=2.0.1` | **Low** | AST/frame inspection; CPython-internal access | Acceptable; lockfile mitigates |
| `cryptography` | `>= 44.0.0` (dev) | **Low** | Used in tests; floor is recent | Run pip-audit periodically |
| `claude-agent-sdk` | `>= 0` (dev) | **Low** | Emerging package; no version floor | Add floor version |
| `aiohttp` | `3.13.3` (locked) | **Low** | C extension; network library | Keep lockfile current |

---

## Lockfile Health Summary

```
✅ uv.lock present and committed
✅ Full transitive dependency graph covered  
✅ SHA256 integrity hashes for all artifacts
✅ All sources point to https://pypi.org/simple
✅ exclude-newer freshness window (P1W) prevents accidental new package injection
✅ uv sync --frozen used in CI lint and test jobs
⚠️  docs build job bypasses lockfile (--upgrade + private registry)
⚠️  mkdocs-material and mkdocstrings-python bypass freshness window
⚠️  hatchling build backend not in lockfile scope for PEP 517 builds
```

---

## Recommended Dependabot Configuration

```yaml
# .github/dependabot.yml
version: 2
updates:
  # Python dependencies (uv ecosystem)
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    groups:
      opentelemetry:
        patterns:
          - "opentelemetry-*"
      openinference:
        patterns:
          - "openinference-*"

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
```

---

## SBOM Generation Commands

```bash
# Option 1: CycloneDX (recommended — machine-readable, widely supported)
pip install cyclonedx-bom
uv run cyclonedx-py environment --of JSON --output-file sbom-cyclonedx.json

# Option 2: Using uv pip list (simple SPDX-like text)
uv pip list --format=json > sbom-packages.json

# Option 3: pip-licenses (human-readable with license info)
uv run pip-licenses --format=markdown --with-urls --output-file THIRD_PARTY_LICENSES.md

# Option 4: syft (supply chain tool, produces SPDX/CycloneDX)
syft dir:. -o spdx-json=sbom.spdx.json
```

---

## Vulnerability Scan Commands

```bash
# pip-audit — checks locked packages against OSV and PyPI Advisory DB
uv run pip-audit

# safety — checks against Safety DB
uv run safety check

# Using pip audit directly on the lockfile:
pip-audit --requirement <(uv export --format=requirements-txt --frozen)

# For the GitHub Actions audit, use actionlint:
actionlint .github/workflows/*.yml
```

---

## Prioritised Remediation Roadmap

### Immediate (within 1 sprint)

1. **[H-01]** Pin `pypa/gh-action-pypi-publish` and `re-actors/alls-green` to commit SHAs — these are in the release critical path.  
2. **[H-03]** Pin all other GitHub Actions to commit SHAs across all workflow files.  
3. **[H-02]** Restrict `claude.yml` trigger to maintainer-only and remove `id-token: write` if not needed.

### Short-term (within 1 month)

4. **[M-01]** Add a version constraint to `hatchling` in `[build-system]`.  
5. **[M-02]** Pin `pydantic-docs` to a specific commit SHA.  
6. **[M-06]** Add `dependabot.yml` for both pip and GitHub Actions.  
7. **[L-04]** Raise `protobuf` lower bound to `>= 4.25.4`.  
8. Run `pip-audit` and review CVE findings against the current `uv.lock` state.

### Medium-term (within 1 quarter)

9. **[M-04]** Add SLSA L3 provenance via `slsa-github-generator` to the release workflow.  
10. **[L-01]** Add SBOM generation to the release pipeline.  
11. **[M-03]** Move docs packages to the public lockfile or document the private registry dependency clearly.  
12. **[M-07]** Add version floors to `openinference-instrumentation-*` optional deps.

---

## SDL Compliance Summary

| SDL Phase | Finding IDs | Status |
|---|---|---|
| **Requirements** | — | ✅ No issues identified |
| **Design** | H-02 | ⚠️ Claude workflow privilege design |
| **Implementation** | M-01, M-02, M-07, L-03, L-04, L-05 | ⚠️ Multiple dependency pinning issues |
| **Verification** | H-01, H-03, M-03, M-05, M-06 | 🔴 CI/CD action pinning; no automated CVE scanning |
| **Release** | M-04, L-01 | ⚠️ No SLSA provenance; no SBOM |
| **Response** | M-06 | ⚠️ No automated vulnerability alerting |

---

*Report generated by Supply Chain Security Agent — Microsoft SDL-aligned*  
*Timestamp: 2025-07-14*  
*Scope: logfire v4.31.0, logfire-api v4.31.0*  
*Tools referenced: uv, pip-audit, safety, cyclonedx-bom, syft, actionlint, slsa-github-generator, Dependabot*
