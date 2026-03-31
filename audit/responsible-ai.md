# Responsible AI Audit Report — Logfire Python SDK

**Date**: 2025-07-15  
**Auditor**: Responsible AI Audit Agent (Microsoft SDL-aligned)  
**Project**: `logfire` v4.31.0  
**Scope**: Open-source Python SDK — LLM instrumentation wrappers, AI provider integrations, telemetry pipeline, ML supply chain  
**Architecture Reference**: `audit/ARCHITECTURE.md`  
**Threat Model Reference**: `audit/THREAT_MODEL.md`  
**SDL Methodology**: Findings mapped to Requirements / Design / Implementation / Verification phases  
**Severity Scale**: Critical → High → Medium → Low  

---

## Table of Contents

1. [AI/ML Component Inventory](#1-aiml-component-inventory)
2. [Audit Scope & Methodology](#2-audit-scope--methodology)
3. [Critical Findings](#3-critical-findings)
4. [High Findings](#4-high-findings)
5. [Medium Findings](#5-medium-findings)
6. [Low Findings](#6-low-findings)
7. [Positive RAI Controls Already Present](#7-positive-rai-controls-already-present)
8. [Fairness Assessment](#8-fairness-assessment)
9. [Transparency Checklist](#9-transparency-checklist)
10. [Content Safety Assessment](#10-content-safety-assessment)
11. [Human Oversight Assessment](#11-human-oversight-assessment)
12. [ML Supply Chain Assessment](#12-ml-supply-chain-assessment)
13. [Regulatory Gap Analysis](#13-regulatory-gap-analysis)
14. [Findings Summary Table](#14-findings-summary-table)
15. [Recommendations Roadmap](#15-recommendations-roadmap)

---

## 1. AI/ML Component Inventory

The Logfire SDK does not implement AI/ML models itself. It provides **instrumentation wrappers** that intercept calls to external AI/ML services and capture telemetry (OTel spans, logs, metrics). Additionally, the Logfire platform's CLI exposes AI-powered features.

| ID | Component | Framework / Provider | Purpose | Location | Data Captured |
|----|-----------|---------------------|---------|----------|---------------|
| AI-01 | OpenAI instrumentation | `openai` SDK (monkey-patch) | Capture chat completions, text completions, embeddings, image generation as OTel spans | `logfire/_internal/integrations/llm_providers/openai.py` | Full request JSON (`request_data`), full response (`response_data`), token usage, model name, finish reasons; in `'latest'` mode: `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions` |
| AI-02 | Anthropic instrumentation | `anthropic` SDK (monkey-patch) | Capture Claude API calls (messages, streaming, Bedrock) as OTel spans | `logfire/_internal/integrations/llm_providers/anthropic.py` | Full request JSON (`request_data`), full response (`response_data`), token usage (including cache tokens), model name, stop reason; in `'latest'` mode: `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions` |
| AI-03 | LLM provider base | Internal | Shared GenAI OTel semantic convention constants, `StreamState` base class, `EndpointConfig` | `logfire/_internal/integrations/llm_providers/{llm_provider,semconv,types}.py` | N/A (infrastructure only) |
| AI-04 | Google Generative AI instrumentation | `opentelemetry-instrumentation-google-genai` (third-party) | Instrument Google Gemini API calls | `logfire/_internal/integrations/google_genai.py` | Prompt/completion content (opt-in via `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`), token usage, model metadata |
| AI-05 | LiteLLM instrumentation | `openinference-instrumentation-litellm` (third-party) | Instrument LiteLLM multi-provider proxy calls | `logfire/_internal/integrations/litellm.py` | Delegated to OpenInference instrumentor; content capture behaviour varies |
| AI-06 | DSPy instrumentation | `openinference-instrumentation-dspy` (third-party) | Instrument DSPy LM programs | `logfire/_internal/integrations/dspy.py` (inferred from architecture) | Delegated to OpenInference instrumentor |
| AI-07 | OpenAI Agents SDK instrumentation | `agents` / `openai-agents` package | Convert OpenAI Agents trace events to OTel spans; captures agent, generation, function, handoff, voice span types | `logfire/_internal/integrations/openai_agents.py` | Agent inputs/outputs, generation events, function call arguments/results |
| AI-08 | Pydantic AI instrumentation | `pydantic-ai-slim` | Hook into Pydantic AI's OTel instrumentation; delegates to `InstrumentationSettings` | `logfire/_internal/integrations/pydantic_ai.py` | Prompts, completions, tool call arguments/responses (opt-out via `include_content=False`) |
| AI-09 | Claude Agent SDK instrumentation | `claude-agent-sdk` | Hook-based capture of Anthropic Claude Code agent runs | `logfire/_internal/integrations/claude_agent_sdk.py` | Full conversation (INPUT_MESSAGES, OUTPUT_MESSAGES, SYSTEM_INSTRUCTIONS), tool call arguments/results, thinking blocks |
| AI-10 | MCP instrumentation | `mcp` package | Instrument Model Context Protocol JSON-RPC sessions | `logfire/_internal/integrations/mcp.py` | Full request/response bodies for all MCP method calls including `tools/call` |
| AI-11 | AI evals API client | `pydantic-evals` (optional dep) | Manage AI evaluation datasets and test cases stored in Logfire platform | `logfire/experimental/api_client.py` | Eval inputs, expected outputs, eval case metadata |
| AI-12 | AI evaluation annotations | Internal | Annotate OTel spans with AI evaluation outcomes (pass/fail/score/feedback) | `logfire/experimental/annotations.py` | Feedback name, value, comment attached to traced spans |
| AI-13 | `logfire prompt` CLI | Logfire platform AI (Claude/other) | Fetch AI-agent prompt for a Logfire issue; used by Claude Code, Codex, OpenCode | `logfire/_internal/cli/prompt.py` | Issues/PRs from Logfire platform processed by external AI |

---

## 2. Audit Scope & Methodology

This audit covers:

- **Phase 2**: Fairness & Bias — feature capture, demographic proxies, evaluation tooling
- **Phase 3**: Transparency & Explainability — model documentation, decision logging, disclosure
- **Phase 4**: Content Safety — output filtering, prompt injection, PII in prompts
- **Phase 5**: Human Oversight & Control — human-in-the-loop, kill switches, override mechanisms
- **Phase 6**: ML Supply Chain — model provenance, dependency pinning, deserialization safety
- **Phase 7**: Regulatory Alignment — EU AI Act, NIST AI RMF, GDPR Art. 22, Microsoft RAI Standard

Evidence base: static analysis of source code at `logfire/` and `logfire/_internal/integrations/`, architecture document, threat model, and `pyproject.toml`.

---

## 3. Critical Findings

---

### [CRITICAL] — C-01: Scrubbing Pipeline Completely Disabled for OpenAI and Anthropic Spans

- **SDL Phase**: Implementation
- **Category**: Privacy & Security (Microsoft RAI Standard: Privacy & Security)
- **File**: `logfire/_internal/scrubbing.py` — lines 200–202
- **Description**:

  The `Scrubber.scrub_span()` method contains an explicit early-return bypass for all spans whose `instrumentation_scope.name` is `'logfire.openai'` or `'logfire.anthropic'`:

  ```python
  def scrub_span(self, span: ReadableSpanDict):
      scope = span['instrumentation_scope']
      if scope and scope.name in ['logfire.openai', 'logfire.anthropic']:
          return   # <-- entire scrubbing pipeline is skipped
  ```

  This means **all default scrubbing patterns** — including `password`, `secret`, `api_key`, `auth`, `credential`, `jwt`, `ssn`, `credit_card`, `cookie`, `private_key` — are **never applied** to LLM spans. A developer sending a user's API key, social security number, or session token as context to an LLM will have that data captured in a span attribute, transmitted to the Logfire SaaS backend over HTTPS, and persisted indefinitely with no redaction.

  Concrete example: `openai.chat.completions.create(messages=[{"role":"user","content":"My SSN is 123-45-6789, help me..."}])` — the entire prompt is stored verbatim in `request_data` on the span.

  This bypass appears to be intentional (to avoid false-positive scrubbing of prompts discussing passwords/keys), but it is not documented, has no opt-in restore path, and silently negates the SDK's privacy protection for the most sensitive data category it captures.

- **Affected Users**: All end-users of instrumented applications whose prompts or LLM context windows may contain PII, credentials, or sensitive business data. Also affects Logfire platform operators who store this data.
- **Standard Reference**: Microsoft RAI Standard — Privacy & Security; GDPR Art. 4(1) (personal data), Art. 5(1)(f) (integrity/confidentiality); NIST AI RMF — GOVERN 1.7 (processes for privacy risk)
- **Recommendation**:
  1. **Remove the blanket scope bypass.** Instead, apply scrubbing to `request_data` and other non-content attributes on LLM spans.
  2. Add `'request_data'`, `'response_data'`, and other LLM-specific top-level attributes to the scrubber's traversal path so that nested keys like `messages[].content` are evaluated.
  3. For `gen_ai.input.messages` / `gen_ai.output.messages` (already in `SAFE_KEYS`): provide a configurable option `scrub_llm_content: bool = True` on `ScrubbingOptions` so operators can enable deep content scrubbing when required by their data classification policy.
  4. Document the bypass behaviour prominently in the scrubbing docs.

---

### [CRITICAL] — C-02: No Opt-Out Mechanism for LLM Prompt/Response Capture in OpenAI and Anthropic Instrumentation

- **SDL Phase**: Design
- **Category**: Privacy & Security (Microsoft RAI Standard: Privacy & Security; Transparency)
- **File**: `logfire/_internal/main.py` — `instrument_openai()` (line ~1224), `instrument_anthropic()` (line ~1328)
- **Description**:

  `instrument_openai()` and `instrument_anthropic()` **unconditionally capture the full prompt and response content** and provide no parameters to disable this behaviour:

  ```python
  def instrument_openai(
      self,
      openai_client=None,
      *,
      suppress_other_instrumentation: bool = True,
      version: SemconvVersion | Sequence[SemconvVersion] = 1,
  ) -> AbstractContextManager[None]:
  ```

  No `capture_input`, `capture_output`, or `include_content` parameter exists. Every call to `client.chat.completions.create()` will record the complete `messages` array (system prompt, conversation history, user input) and the complete model response as span attributes.

  This is inconsistent with the SDK's own approach for other AI providers:
  - **Pydantic AI**: `instrument_pydantic_ai(include_content=False)` available
  - **Google GenAI**: Content capture requires explicit opt-in via `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`
  - **OpenAI / Anthropic**: Content is always captured, no opt-out

  Developers building multi-tenant SaaS products, healthcare apps, or legal tools may have strong regulatory and contractual obligations not to log user-provided natural-language inputs. There is no way to comply with these obligations while still using Logfire's OpenAI/Anthropic instrumentation.

- **Affected Users**: Users of instrumented applications (their conversational input is captured); developers who cannot comply with data minimisation requirements; organisations subject to HIPAA, GDPR, or contractual data handling restrictions.
- **Standard Reference**: Microsoft RAI Standard — Privacy & Security; GDPR Art. 5(1)(c) (data minimisation); EU AI Act Art. 12 (record-keeping for high-risk AI); NIST AI RMF — MAP 2.2 (data privacy risks identified)
- **Recommendation**:
  1. Add `capture_input: bool = True` and `capture_output: bool = True` parameters to both `instrument_openai()` and `instrument_anthropic()`, mirroring the Pydantic AI pattern.
  2. When `capture_input=False`, omit `request_data.messages`, `gen_ai.input.messages`, and `gen_ai.system_instructions` from the span.
  3. When `capture_output=False`, omit `response_data.message`, `gen_ai.output.messages` from the span.
  4. Add corresponding `LOGFIRE_INSTRUMENT_OPENAI_CAPTURE_INPUT` / `LOGFIRE_INSTRUMENT_OPENAI_CAPTURE_OUTPUT` environment variables so this can be controlled at deployment time.
  5. Document the data-capture behaviour and privacy implications prominently in the OpenAI and Anthropic integration guides.

---

## 4. High Findings

---

### [HIGH] — H-01: LLM Message Content Attributes Exempted from Scrubbing in SAFE_KEYS

- **SDL Phase**: Implementation
- **Category**: Privacy & Security
- **File**: `logfire/_internal/scrubbing.py` — lines 111–160 (`BaseScrubber.SAFE_KEYS`)
- **Description**:

  The following LLM-specific span attribute keys are listed in `BaseScrubber.SAFE_KEYS`, which unconditionally prevents the scrubber from recursing into their values:

  ```python
  SAFE_KEYS = {
      ...
      'gen_ai.input.messages',       # full prompt conversation history
      'gen_ai.output.messages',      # full model response
      'gen_ai.system_instructions',  # system prompt
      'pydantic_ai.all_messages',    # all messages in a Pydantic AI run
      ...
  }
  ```

  Even if the blanket scope bypass (C-01) were removed, these attributes would still never be scrubbed. A user sending a message containing `"my password is hunter2"` in their LLM prompt would have that stored verbatim in `gen_ai.input.messages`. This creates a defence-in-depth failure: C-01 and H-01 together mean there are **two independent mechanisms** that both prevent scrubbing of LLM content.

  The rationale for `SAFE_KEYS` exclusion is legitimate for most attributes (avoiding accidental over-scrubbing of semantic keys), but applying it to the entire message content objects is over-broad.

- **Affected Users**: Same as C-02 — all end-users whose natural-language input may contain sensitive data.
- **Standard Reference**: Microsoft RAI Standard — Privacy & Security; GDPR Art. 5(1)(f)
- **Recommendation**:
  1. Remove `'gen_ai.input.messages'`, `'gen_ai.output.messages'`, `'gen_ai.system_instructions'`, and `'pydantic_ai.all_messages'` from `SAFE_KEYS`.
  2. Instead, introduce a configurable `scrub_llm_content` flag (see C-01 recommendation) to give operators control.
  3. When `scrub_llm_content=True` (opt-in), traverse message part `content` strings through the scrubber.
  4. Log a clear warning in documentation that LLM message content is not scrubbed by default and explain the trade-off.

---

### [HIGH] — H-02: Binary / Image / Audio Blob Content Captured in Spans Without Restrictions

- **SDL Phase**: Design
- **Category**: Privacy & Security; Content Safety
- **File**: `logfire/_internal/integrations/llm_providers/semconv.py` (`BlobPart`, `UriPart`); `logfire/_internal/integrations/llm_providers/openai.py` (`_convert_content_part`); `logfire/_internal/integrations/llm_providers/anthropic.py` (`_convert_content_part`)
- **Description**:

  Both OpenAI and Anthropic instrumentation convert multimodal content (images, audio) into span attributes:

  ```python
  # openai.py: image_url parts
  return UriPart(type='uri', uri=url, modality='image')

  # openai.py: audio parts
  return BlobPart(type='blob', content=part.get('input_audio', {}).get('data', ''), modality='audio')

  # anthropic.py: base64 image parts
  blob_part = BlobPart(type='blob', modality='image', content=source.get('data', ''))
  ```

  Base64-encoded binary content can be arbitrarily large (multi-MB images) and may contain:
  - Personally identifiable photos of individuals
  - Medical imaging (HIPAA-protected)
  - Audio recordings of conversations (biometric data under GDPR)
  - Other sensitive visual or audio data

  There is no size cap on `BlobPart.content`, no content-type allowlist, and no opt-out for binary content separate from text content. The `instrument_pydantic_ai(include_binary_content=False)` parameter demonstrates the SDK authors are aware of this concern for Pydantic AI, but OpenAI and Anthropic have no equivalent.

- **Affected Users**: Users who submit images or audio to multimodal LLMs (e.g., medical records photos, biometric audio).
- **Standard Reference**: Microsoft RAI Standard — Privacy & Security; GDPR Art. 9 (special category biometric data); HIPAA Safe Harbor
- **Recommendation**:
  1. Add `capture_images: bool = False` and `capture_audio: bool = False` parameters to `instrument_openai()` and `instrument_anthropic()`, defaulting to `False` (privacy-safe default).
  2. When a `BlobPart` is encountered and the corresponding capture flag is `False`, replace `content` with a placeholder string (e.g., `"[image content redacted]"`) and retain only `modality` and `media_type`.
  3. Apply a maximum size limit to `BlobPart.content` (e.g., 64 KB) as a safety net.

---

### [HIGH] — H-03: No Content Safety Filtering on AI-Generated Outputs

- **SDL Phase**: Design
- **Category**: Content Safety (Microsoft RAI Standard: Reliability & Safety)
- **File**: Architecture-level — no content safety layer exists in the instrumentation pipeline
- **Description**:

  The SDK captures LLM responses (from OpenAI, Anthropic, Google, LiteLLM, Pydantic AI, Claude Agent SDK) and stores them as span attributes and logs. At no point in the instrumentation pipeline is there:
  - A toxicity classifier or harm detector applied to LLM outputs
  - A content policy check before storage
  - Any mechanism to flag, redact, or alert on unsafe AI-generated content

  This is not a traditional content moderation problem (the SDK is an observability tool, not a content proxy), but it does mean the Logfire backend accumulates potentially harmful AI outputs with no filtering. For applications using AI output classification (e.g., sentiment analysis on user complaints, content scoring) the spans contain the raw outputs with no safety envelope.

  Furthermore, the `record_feedback` annotation API and `LogfireAPIClient` eval datasets store model inputs/outputs for AI evaluation workflows — these datasets could accumulate harmful content over time with no automated review.

- **Affected Users**: Logfire platform operators; developers reviewing AI eval datasets; any user whose data flows through an AI system being monitored.
- **Standard Reference**: Microsoft RAI Standard — Reliability & Safety; NIST AI RMF — MEASURE 2.5 (AI system outputs monitored for safety)
- **Recommendation**:
  1. Provide an optional `output_safety_callback: Callable[[str], bool] | None = None` parameter on `instrument_openai()` / `instrument_anthropic()` / `instrument_pydantic_ai()` that applications can use to hook in content safety classifiers.
  2. Document that the SDK does not perform content safety analysis and direct users to Azure AI Content Safety or equivalent services.
  3. Consider adding a `max_content_length` parameter to truncate extremely long responses before storage (prevents denial of service via large span payloads, not just safety).

---

### [HIGH] — H-04: Unpinned AI Instrumentation Library Dependencies Enable Silent Supply Chain Substitution

- **SDL Phase**: Implementation
- **Category**: ML Supply Chain (Microsoft RAI Standard: Reliability & Safety)
- **File**: `pyproject.toml` — lines 84–85
- **Description**:

  Two third-party AI instrumentation packages have completely unconstrained version ranges:

  ```toml
  litellm = ["openinference-instrumentation-litellm >= 0"]
  dspy   = ["openinference-instrumentation-dspy >= 0"]
  ```

  The `>= 0` constraint means any future version — including one with breaking changes to data capture behaviour, removed privacy controls, or a compromised release — will be silently accepted. These are **supply chain components that process sensitive LLM prompt/response data**. A malicious or accidentally broken release could:
  - Begin exfiltrating prompt content to an attacker-controlled endpoint
  - Remove content filtering
  - Introduce remote code execution via unsafe model file deserialization

  Additionally, `openai` and `anthropic` themselves are not declared as optional dependencies in `pyproject.toml` at all — they are expected to be user-installed, meaning Logfire has no visibility into which version of these critical packages is running. The `uv.lock` lockfile does pin transitive dependencies for development/CI, but the `pyproject.toml` version floors only apply to end-user installations.

- **Affected Users**: All users of Logfire's LiteLLM and DSPy integrations.
- **Standard Reference**: Microsoft SDL — Supply Chain Security; NIST AI RMF — GOVERN 6.2 (AI supply chain risks); NIST SP 800-218 SSDF PW.4
- **Recommendation**:
  1. Replace `>= 0` with a minimum known-good version and an upper bound: e.g., `openinference-instrumentation-litellm >= 0.30.0, < 1.0.0`.
  2. Add `openai >= 1.0.0, < 2.0.0` and `anthropic >= 0.20.0` as optional dependency version constraints under an `openai` / `anthropic` extras group.
  3. Enable `uv lock --check` or `pip-audit` in CI to detect known vulnerabilities in AI SDK dependencies.
  4. Subscribe to security advisories for `openai`, `anthropic`, `openinference-instrumentation-*` packages.

---

## 5. Medium Findings

---

### [MEDIUM] — M-01: Inconsistent LLM Content Capture Controls Across AI Providers

- **SDL Phase**: Design
- **Category**: Transparency; Privacy & Security
- **File**: `logfire/_internal/main.py` — multiple `instrument_*` methods
- **Description**:

  Content capture controls are inconsistent across providers, making it impossible to apply uniform data governance:

  | Provider | Capture Control | Default |
  |----------|----------------|---------|
  | OpenAI | ❌ No opt-out | Always on |
  | Anthropic | ❌ No opt-out | Always on |
  | Claude Agent SDK | ❌ No opt-out | Always on |
  | Pydantic AI | ✅ `include_content=False` | On (opt-out available) |
  | Google GenAI | ✅ `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` | **Off** (opt-in required) |
  | LiteLLM | ❓ Unknown (third-party) | Varies |
  | DSPy | ❓ Unknown (third-party) | Varies |
  | MCP | ❌ No opt-out | Always on |

  An organisation wishing to implement a policy of "capture metadata only, not content" cannot do so uniformly across all Logfire AI integrations — even if they configure Pydantic AI correctly, the OpenAI SDK used by the same agent will still capture full content.

- **Affected Users**: Developers subject to data minimisation requirements; security-conscious operators managing multi-provider AI stacks.
- **Standard Reference**: Microsoft RAI Standard — Privacy & Security; GDPR Art. 5(1)(c); NIST AI RMF — MAP 2.2
- **Recommendation**:
  1. Introduce a global `capture_llm_content: bool = True` parameter on `logfire.configure()` that acts as a master switch for all LLM content capture across all providers.
  2. Document the data capture behaviour and opt-out path in a dedicated "Privacy and LLM Data" section of the documentation.
  3. Expose `LOGFIRE_CAPTURE_LLM_CONTENT=false` as an environment variable for deployment-time control.

---

### [MEDIUM] — M-02: MCP Tool Call Arguments and Results Captured Without Filtering

- **SDL Phase**: Design
- **Category**: Privacy & Security; Content Safety
- **File**: `logfire/_internal/integrations/mcp.py` — lines 37–58
- **Description**:

  The MCP integration captures the full request and response for every MCP JSON-RPC call:

  ```python
  attributes: dict[str, Any] = {
      'request': root,    # full CallToolRequest including all arguments
      ...
  }
  with logfire_instance.span(span_name, **attributes) as span:
      ...
      span.set_attribute('response', result)  # full server response
  ```

  MCP tool calls can include:
  - File system operations with full file paths and content
  - Database queries with result sets containing PII
  - External API calls with credentials or sensitive parameters
  - User-submitted content passed to tools as arguments

  Additionally, MCP is designed as an injection attack surface — a malicious MCP server can return adversarially crafted tool results. Capturing these verbatim in spans provides a pathway for prompt injection payloads to be stored in the Logfire backend, potentially affecting AI systems that query telemetry data.

- **Affected Users**: Users of MCP-connected applications; developers whose tool results may contain PII or sensitive data.
- **Standard Reference**: Microsoft RAI Standard — Privacy & Security; OWASP LLM Top 10 — LLM02 (Insecure Output Handling)
- **Recommendation**:
  1. Apply the same `capture_input`/`capture_output` controls to `instrument_mcp()` as recommended for OpenAI/Anthropic.
  2. Apply content scrubbing to MCP tool call arguments and results (do not bypass with scope-based exemption).
  3. Document the prompt injection risk of capturing MCP tool results verbatim.

---

### [MEDIUM] — M-03: No Model Card or System Card for Logfire's AI-Powered Features

- **SDL Phase**: Requirements
- **Category**: Transparency (Microsoft RAI Standard: Transparency; Accountability)
- **File**: Architecture-level — `logfire/_internal/cli/prompt.py`; `.github/workflows/claude.yml`
- **Description**:

  Logfire exposes several AI-powered features to users:

  1. **`logfire prompt` CLI command** (`cli/prompt.py`): Fetches AI-agent prompts from the Logfire platform, which are generated using Claude (evidenced by `.github/workflows/claude.yml`). Users executing `logfire prompt` receive AI-generated content but are not told which AI model produced it, what its limitations are, or what data was used to train it.

  2. **AI evaluation framework** (`experimental/api_client.py`, `experimental/annotations.py`): Provides an evals platform for AI systems but includes no guidance on bias evaluation, fairness testing, or responsible deployment of the AI systems being evaluated.

  3. **Claude-powered GitHub workflow** (`.github/workflows/claude.yml`): Claude AI automatically processes issues and PRs for this open-source project. Contributors receive AI-generated responses without disclosure.

  No model card, system card, or datasheet exists for any of these AI-powered features.

- **Affected Users**: All Logfire SDK users who interact with the `logfire prompt` CLI; GitHub contributors receiving Claude-generated responses; developers building AI systems using the evals platform.
- **Standard Reference**: Microsoft RAI Standard — Transparency; Model Cards for Model Reporting (Mitchell et al. 2019); EU AI Act Art. 13 (transparency obligations); NIST AI RMF — GOVERN 1.1
- **Recommendation**:
  1. Create a brief model card / system card for each AI-powered feature, covering: model name and version, intended use, data used, known limitations, feedback mechanism.
  2. Add a disclosure to `logfire prompt` command output: e.g., `"This prompt was generated by [model name]. Review carefully before use."`.
  3. Add a disclosure in the GitHub issue template when Claude is responding: this is best practice and increasingly required under EU AI Act transparency obligations.

---

### [MEDIUM] — M-04: No Fairness Evaluation Support in AI Evals Framework

- **SDL Phase**: Design
- **Category**: Fairness & Bias (Microsoft RAI Standard: Fairness; Inclusiveness)
- **File**: `logfire/experimental/api_client.py`; `logfire/experimental/annotations.py`
- **Description**:

  The `LogfireAPIClient` evals API and `record_feedback` annotation system provide structured support for:
  - Pass/fail assertions
  - Numeric scores
  - String labels
  - Comments

  But there is no structured support for:
  - **Demographic metadata on eval cases** — no fields for user demographic group, locale, or other attributes needed for disaggregated fairness analysis
  - **Fairness-specific metrics** — no built-in evaluators for demographic parity, equal opportunity, equalized odds
  - **Subgroup performance tracking** — no mechanism to aggregate eval outcomes by user group
  - **Bias detection hooks** — no documentation or API to detect bias in AI outputs being evaluated

  Developers using Logfire to evaluate their AI systems have no structured pathway to conduct fairness audits. This is a gap because the evals framework explicitly positions itself as an AI quality management tool.

- **Affected Users**: Developers who rely on Logfire evals to certify AI quality; downstream end-users of AI systems evaluated via Logfire; any demographic group that may be differentially affected by the AI systems being monitored.
- **Standard Reference**: Microsoft RAI Standard — Fairness & Inclusiveness; EU AI Act Art. 10(2)(f) (examination of training data for bias); NIST AI RMF — MEASURE 2.5
- **Recommendation**:
  1. Add optional `metadata: dict[str, Any]` fields to `Case` objects specifically designed to hold demographic or subgroup identifiers.
  2. Provide documentation guidance on using the evals framework for fairness testing (e.g., disaggregating eval scores by demographic fields).
  3. Consider adding built-in evaluators for demographic parity and equal opportunity to `pydantic-evals`.
  4. Add a "Fairness Evaluation" section to the AI evals documentation with worked examples.

---

### [MEDIUM] — M-05: No Human-in-the-Loop or Escalation Mechanism for High-Stakes AI Decisions

- **SDL Phase**: Design
- **Category**: Human Oversight (Microsoft RAI Standard: Accountability; Reliability & Safety)
- **File**: Architecture-level
- **Description**:

  The SDK provides no mechanisms to support human oversight of AI-driven decisions:

  - **No response flagging**: No API to mark an AI response as requiring human review
  - **No kill switch at the instrumentation layer**: AI provider instrumentation cannot be selectively disabled without modifying application code (no feature-flag integration)
  - **No circuit breaker**: No mechanism to detect high error rates, unusual latency, or anomalous output patterns and automatically pause AI calls
  - **No rate limiting hooks**: No built-in support for per-user or per-tenant rate limiting of AI endpoints
  - **No escalation path**: No structured span attribute or metric to indicate that an AI decision should be escalated to a human

  While these are application-level concerns, observability SDKs are uniquely positioned to surface them — the SDK already captures the full span lifecycle and could expose hooks for applications to implement oversight.

- **Affected Users**: End-users of AI systems making consequential decisions (hiring, lending, medical, legal, law enforcement).
- **Standard Reference**: Microsoft RAI Standard — Accountability; EU AI Act Art. 14 (human oversight); NIST AI RMF — GOVERN 5.1 (human oversight)
- **Recommendation**:
  1. Add a `requires_human_review: bool` span attribute convention to the AI semantic conventions (e.g., `gen_ai.requires_review`).
  2. Document patterns for implementing human-in-the-loop using Logfire's existing feedback and annotation APIs.
  3. Add an example in documentation showing how to use `record_feedback` to flag AI decisions for review.
  4. Consider adding a `logfire.instrument_openai(rate_limit_callback=...)` hook to enable rate limiting.

---

### [MEDIUM] — M-06: `logfire prompt` CLI Fetches AI-Generated Content Without Model Disclosure

- **SDL Phase**: Requirements
- **Category**: Transparency (Microsoft RAI Standard: Transparency)
- **File**: `logfire/_internal/cli/prompt.py`
- **Description**:

  The `logfire prompt` CLI subcommand fetches AI-agent prompts from the Logfire platform. These prompts are used to configure AI coding assistants (Claude Code, Codex, OpenCode). The source of these prompts — which AI model generated them, with what data, under what safety constraints — is not disclosed to the developer receiving them.

  A developer acting on an AI-generated prompt has no way to assess:
  - Whether the prompt contains hallucinated or incorrect information
  - Which model version produced the prompt
  - What the model's known failure modes are in this context

- **Affected Users**: Developers using `logfire prompt` to configure AI coding assistants.
- **Standard Reference**: EU AI Act Art. 52(1) (disclosure obligation for AI-generated content); Microsoft RAI Standard — Transparency
- **Recommendation**:
  1. Include model attribution in the output of `logfire prompt` (e.g., `"Generated by Claude claude-3-5-sonnet-20241022"`).
  2. Add a disclaimer that the prompt is AI-generated and should be reviewed before use.
  3. Version-stamp prompts so developers can track when the underlying AI model changed.

---

## 6. Low Findings

---

### [LOW] — L-01: EU AI Act Risk Classification Not Performed

- **SDL Phase**: Requirements
- **Category**: Regulatory Gap
- **File**: Architecture-level
- **Description**:

  No EU AI Act risk classification has been performed for the Logfire SDK's AI instrumentation components or the Logfire platform's AI-powered features. Under the EU AI Act:

  - **`logfire prompt` CLI**: Likely "limited risk" (Art. 52) — transparency obligations apply (disclosure that content is AI-generated).
  - **AI evals framework**: If used to evaluate AI systems in high-risk categories (hiring, credit scoring, medical), it may itself be subject to high-risk requirements or at minimum should document that it's not a conformity assessment tool.
  - **LLM instrumentation capturing personal data**: Interacts with potentially high-risk AI systems, with data processing implications under Art. 10 (data governance).

  No documentation addresses which risk tier applies to the SDK or its components.

- **Affected Users**: Organisations deploying Logfire in the EU or processing data of EU persons.
- **Standard Reference**: EU AI Act Art. 6–7 (high-risk classification), Art. 52 (limited-risk transparency), Art. 53 (general-purpose AI)
- **Recommendation**:
  1. Conduct a formal EU AI Act classification exercise for each AI-powered feature.
  2. Add an "EU AI Act Compliance Notes" section to the documentation addressing risk tiers and applicable obligations.
  3. Ensure the Logfire platform (out of scope for this audit) has a corresponding DPA and data processing agreements.

---

### [LOW] — L-02: No AI Model Version Fingerprinting for Reproducibility

- **SDL Phase**: Verification
- **Category**: ML Supply Chain; Transparency
- **File**: `logfire/_internal/integrations/llm_providers/semconv.py`; `openai.py`; `anthropic.py`
- **Description**:

  The SDK captures `gen_ai.request.model` (the model name requested, e.g., `"gpt-4"`) and `gen_ai.response.model` (the actual model used, e.g., `"gpt-4-0613"`). However:

  - No model version hash or fingerprint is captured
  - Provider-specific version identifiers (e.g., OpenAI's `system_fingerprint`) are not consistently recorded
  - There is no mechanism to detect when a model is silently updated by the provider (model drift)

  This limits the ability to reproduce AI system behaviour during incident investigations or bias audits.

  Note: OpenAI includes `system_fingerprint` in responses to identify the infrastructure configuration; this field is not currently extracted.

- **Affected Users**: ML engineers conducting post-incident analysis; AI safety teams auditing model drift; compliance teams requiring audit trails.
- **Standard Reference**: NIST AI RMF — MEASURE 2.7 (AI system performance evaluated); Microsoft RAI Standard — Reliability & Safety
- **Recommendation**:
  1. Extract and record `system_fingerprint` from OpenAI responses as `gen_ai.response.system_fingerprint`.
  2. Document how to use `gen_ai.response.model` for version tracking and its limitations.
  3. Consider adding a `gen_ai.model_drift_detected` annotation when `gen_ai.request.model != gen_ai.response.model`.

---

### [LOW] — L-03: No Anomaly Detection or Unusual Output Monitoring Hooks

- **SDL Phase**: Design
- **Category**: Human Oversight; Reliability & Safety
- **File**: Architecture-level
- **Description**:

  The SDK captures comprehensive AI telemetry but provides no built-in support for detecting anomalous patterns:

  - Unusually long responses (potential jailbreak or prompt injection exploitation)
  - Unusual finish reasons (e.g., `content_filter`, `length` repeatedly)
  - Sudden changes in token usage patterns (model substitution, prompt injection)
  - High error rate on a specific model endpoint
  - Atypical tool call patterns in agent runs

  While Logfire's SaaS backend may offer alerting, the SDK itself provides no hooks or documented patterns for implementing output monitoring at the application layer.

- **Affected Users**: Operations teams monitoring AI systems in production; safety teams detecting model misbehaviour.
- **Standard Reference**: NIST AI RMF — MEASURE 2.5; Microsoft RAI Standard — Reliability & Safety
- **Recommendation**:
  1. Add documentation examples of using Logfire metrics to build AI anomaly detection dashboards (e.g., alert on `gen_ai.usage.output_tokens` anomalies).
  2. Consider adding a `span_callback` hook to `instrument_openai()` / `instrument_anthropic()` that receives the completed span for custom monitoring logic.
  3. Document the `finish_reason` values captured (including `content_filter`) so operators know how to alert on content safety events.

---

### [LOW] — L-04: GDPR Article 22 Automated Decision-Making Disclosure Gap

- **SDL Phase**: Requirements
- **Category**: Regulatory Gap
- **File**: Architecture-level — documentation
- **Description**:

  GDPR Article 22 requires that individuals be informed when they are subject to automated decision-making with legal or similarly significant effects, including the right to meaningful information about the logic involved. Applications using AI systems instrumented by Logfire (e.g., AI-powered credit scoring, hiring, content moderation) may be required to provide such disclosure and explanation mechanisms.

  The Logfire SDK's evals and annotation APIs could support explainability workflows, but there is no documentation guidance on how to use Logfire to meet Art. 22 obligations (e.g., capturing decision rationale, providing audit trails, enabling subject access requests).

- **Affected Users**: End-users of AI-powered applications built with Logfire instrumentation; developers of such applications subject to GDPR.
- **Standard Reference**: GDPR Art. 22; EU AI Act Art. 13
- **Recommendation**:
  1. Add a "GDPR Art. 22 / Explainability" documentation section explaining how Logfire telemetry can support automated decision audit trails.
  2. Provide sample code for capturing decision rationale as span attributes alongside the AI model output.
  3. Note that telemetry data constitutes a processing activity under GDPR and should be included in the data controller's ROPA.

---

## 7. Positive RAI Controls Already Present

The following responsible AI controls are **already implemented** and should be recognised:

| Control | Location | Assessment |
|---------|----------|------------|
| **Sensitive data scrubbing** | `logfire/_internal/scrubbing.py` | Strong default patterns for credentials, PII abbreviations (SSN, JWT). Configurable with `ScrubbingOptions`. ✅ |
| **Opt-out for Pydantic AI content capture** | `instrument_pydantic_ai(include_content=False)` | Privacy-respecting default with easy opt-out. ✅ |
| **Opt-in for Google GenAI content capture** | `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` | Privacy-safe default (off). ✅ |
| **HTTPS/TLS for all telemetry transport** | `logfire/_internal/exporters/otlp.py` | All OTLP exports use HTTPS to `logfire-us/eu.pydantic.dev`. ✅ |
| **Token scrubbing in default patterns** | `scrubbing.py` `DEFAULT_PATTERNS` includes `logfire[._ -]?token` | Write token is not captured in spans. ✅ |
| **Instrumentation suppression** | `is_instrumentation_suppressed()` in `llm_provider.py` | Allows suppressing LLM spans in nested calls. ✅ |
| **AI eval annotations API** | `logfire/experimental/annotations.py` | `record_feedback` enables structured human evaluation of AI outputs. ✅ |
| **Token usage tracking** | `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` | Supports cost and resource consumption monitoring. ✅ |
| **OTel Gen AI semantic conventions** | `semconv.py` | Alignment with industry-standard attribute naming enables interoperability. ✅ |
| **Uninstrumentation context manager** | `llm_provider.py` `uninstrument_context()` | Allows reverting LLM instrumentation without process restart. ✅ |
| **Operation cost tracking** | `operation.cost` via `genai_prices` | Transparency into AI API cost per operation. ✅ |
| **No AI model weights in codebase** | Architecture | SDK does not embed or train models; no unsafe deserialization risk. ✅ |
| **pytest telemetry suppression** | `logfire/_internal/config.py` | `send_to_logfire=False` when `PYTEST_VERSION` detected; prevents accidental test data transmission. ✅ |

---

## 8. Fairness Assessment

**Verdict: Not Applicable at SDK Layer / Gap at Platform Layer**

The Logfire SDK is an observability library, not a decision-making AI system. It does not:
- Make automated decisions about people
- Use protected attributes as features
- Implement any ML model with output affecting users

However, the SDK is used to instrument AI systems that **may** make such decisions. Fairness concerns arise in two areas:

1. **Evals Framework Fairness Gap (M-04)**: The evals API has no structured fairness evaluation support, limiting its use for bias audits of instrumented AI systems.

2. **Observability Data for Bias Detection**: The captured telemetry data (prompts, responses, token counts, finish reasons) **could** theoretically support bias analysis if developers add appropriate metadata (user group, demographic proxy, etc.) as span attributes. However, the SDK provides no documentation or tooling for this use case.

3. **No Protected Attribute Usage**: No code uses race, gender, age, religion, disability, nationality, or sexual orientation as ML features or filtering criteria. ✅

4. **No Hardcoded Demographic Categories**: No static demographic lists found. ✅

5. **No Discriminatory Decision Thresholds**: The SDK does not apply thresholds to AI scores for consequential decisions. ✅

**Recommendation**: Add a "Responsible AI Monitoring" documentation section explaining how to use Logfire's telemetry to support bias audits of instrumented AI systems.

---

## 9. Transparency Checklist

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Model documentation (model cards) | ❌ Missing | No model cards for `logfire prompt` or AI eval features |
| Decision logging with inputs/outputs | ✅ Present | Full prompt/response captured in spans (with privacy concerns per C-01/C-02) |
| Model version tracking | ⚠️ Partial | `gen_ai.response.model` captured; no `system_fingerprint` |
| Confidence/uncertainty surface | ❌ Missing | Logprobs not captured; no uncertainty quantification |
| User-facing explanation mechanism | ❌ Missing | No SHAP, LIME, or rationale capture API |
| Automated decision disclosure | ❌ Missing | No documentation on GDPR Art. 22 compliance |
| User consent for AI data capture | ❌ Missing | No consent mechanism; content is captured by default |
| Documentation of what data is captured | ⚠️ Partial | API docs describe parameters but no unified privacy notice |
| Opt-out for LLM content capture | ⚠️ Inconsistent | Present for Pydantic AI / Google GenAI; absent for OpenAI / Anthropic |

---

## 10. Content Safety Assessment

The Logfire SDK is not a generative AI product. It does not generate content. However, as an instrumentation layer for LLM-powered applications, the following content safety considerations apply:

| Concern | Status | Detail |
|---------|--------|--------|
| Output filtering of LLM responses | ❌ Not present | SDK passes through all LLM output verbatim (by design) |
| Prompt injection defence | ⚠️ Partial | `suppress_other_instrumentation=True` prevents double-instrumentation; no semantic prompt injection detection |
| PII in prompts sent to AI | ❌ No scrubbing | C-01: LLM spans bypass scrubbing pipeline entirely |
| Binary content safety | ❌ No filtering | H-02: Images/audio captured without content analysis |
| MCP tool result injection risk | ⚠️ Medium | M-02: Malicious tool results stored verbatim in spans |
| Jailbreak detection | ❌ Not present | No detection of adversarial prompt patterns |
| Grounding / RAG citation | N/A | SDK instruments RAG pipelines but doesn't evaluate grounding |

**Key note**: The Google GenAI instrumentation docstring (`instrument_google_genai`) explicitly states that content capture is opt-in via `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`. This demonstrates awareness of the privacy/safety trade-off for LLM content — but this opt-in default is not applied consistently to OpenAI and Anthropic.

---

## 11. Human Oversight Assessment

| Capability | Status | Detail |
|------------|--------|--------|
| Human review flagging API | ❌ Not present | No `gen_ai.requires_review` attribute or equivalent |
| Override mechanism | ❌ Not present | No API to block or modify AI responses via the SDK |
| Appeal/contestability path | ❌ Not present | Not applicable at SDK layer; no documentation guidance |
| Feature flag / kill switch | ⚠️ Partial | `uninstrument_context()` can revert instrumentation; no runtime flag without code changes |
| Rate limiting hooks | ❌ Not present | No per-user or per-tenant rate limiting in SDK |
| Escalation path | ❌ Not present | No structured escalation span attribute |
| Graceful degradation | ✅ Present | `is_instrumentation_suppressed()` prevents cascading failures; errors are caught and logged internally |

---

## 12. ML Supply Chain Assessment

| Control | Status | Detail |
|---------|--------|--------|
| Model weights in codebase | ✅ N/A | No `.onnx`, `.pt`, `.h5`, `.safetensors` files |
| Unsafe `pickle.load()` / `torch.load()` | ✅ Not found | No model deserialization in codebase |
| Model integrity checks (checksums) | ✅ N/A | No embedded models |
| Training data documentation | ✅ N/A | SDK does not train models |
| Committed lockfile | ✅ Present | `uv.lock` pins all transitive dependencies for dev/CI |
| AI provider SDK version pinning | ❌ Missing | `openai`, `anthropic` not in optional deps; `litellm`, `dspy` instrumentors use `>= 0` (H-04) |
| Third-party AI instrumentor vetting | ❌ Not documented | `openinference-instrumentation-*` from Arize AI; no documented vetting process |
| Transport security (HTTPS) | ✅ Present | All OTLP exports use HTTPS |
| Model registry | ✅ N/A | Not applicable |
| Reproducibility of training | ✅ N/A | Not applicable |

---

## 13. Regulatory Gap Analysis

### EU AI Act

| Provision | Applicability | Gap |
|-----------|--------------|-----|
| Art. 6–7 (High-risk classification) | The SDK instruments AI systems; the `logfire prompt` CLI serves AI-generated content | ❌ No risk classification performed (L-01) |
| Art. 13 (Transparency) | `logfire prompt` serves AI-generated content to users | ❌ No disclosure of AI generation or model identity (M-06) |
| Art. 14 (Human oversight) | AI instrumentation for consequential decisions | ❌ No human oversight hooks (M-05) |
| Art. 52(1) (Disclosure obligation) | `logfire prompt` is an AI-generated content service | ❌ No disclosure to developers (M-06) |
| Art. 10 (Data governance) | LLM prompts may contain personal data | ⚠️ Partial — scrubbing exists but bypassed for LLM spans (C-01) |

### NIST AI RMF

| Function | Category | Gap |
|----------|----------|-----|
| GOVERN 1.1 | Policies for responsible AI | ❌ No published RAI policy for Logfire SDK |
| GOVERN 1.7 | Privacy risk processes | ❌ LLM prompt PII bypass not addressed (C-01, C-02) |
| MAP 2.2 | AI privacy risks | ❌ Inconsistent data minimisation controls (M-01) |
| MEASURE 2.5 | AI output monitoring | ❌ No anomaly detection (L-03) |
| MEASURE 2.7 | Performance evaluation | ⚠️ Partial — evals framework present but no fairness support (M-04) |
| MANAGE 2.2 | Incident response | ❌ No documented AI incident response process |

### Microsoft Responsible AI Standard

| Principle | Assessment |
|-----------|------------|
| **Fairness** | ⚠️ Evals framework lacks fairness tooling (M-04); no demographic analysis support |
| **Reliability & Safety** | ⚠️ Scrubbing bypassed for LLM content (C-01); no content safety hooks (H-03) |
| **Privacy & Security** | ❌ Critical gaps in LLM prompt/response privacy (C-01, C-02, H-01, H-02) |
| **Inclusiveness** | ⚠️ No accessibility or multilingual bias evaluation support |
| **Transparency** | ❌ No model cards; inconsistent capture controls; no AI disclosure in CLI (M-03, M-06) |
| **Accountability** | ⚠️ Eval annotations provide accountability trail; no escalation or human oversight hooks |

### GDPR

| Article | Gap |
|---------|-----|
| Art. 5(1)(c) — Data minimisation | ❌ LLM prompts always captured; no minimisation by default (C-02) |
| Art. 5(1)(f) — Integrity/confidentiality | ❌ PII in LLM prompts not scrubbed (C-01) |
| Art. 9 — Special category data | ❌ Biometric audio/image data captured without consent mechanism (H-02) |
| Art. 22 — Automated decision-making | ❌ No guidance on disclosure or explainability (L-04) |

---

## 14. Findings Summary Table

| ID | Severity | SDL Phase | Category | Title | File |
|----|----------|-----------|----------|-------|------|
| C-01 | **Critical** | Implementation | Privacy & Security | Scrubbing disabled for OpenAI/Anthropic spans | `scrubbing.py:200-202` |
| C-02 | **Critical** | Design | Privacy & Security | No opt-out for LLM prompt/response capture | `main.py:1224, 1328` |
| H-01 | **High** | Implementation | Privacy & Security | LLM content attributes in SAFE_KEYS | `scrubbing.py:149-153` |
| H-02 | **High** | Design | Privacy & Security | Binary/image/audio captured without restrictions | `openai.py`, `anthropic.py` |
| H-03 | **High** | Design | Content Safety | No content safety filtering on AI outputs | Architecture-level |
| H-04 | **High** | Implementation | ML Supply Chain | Unpinned AI instrumentation dependencies | `pyproject.toml:84-85` |
| M-01 | **Medium** | Design | Privacy & Transparency | Inconsistent LLM content controls across providers | `main.py` |
| M-02 | **Medium** | Design | Privacy & Security | MCP tool results captured without filtering | `mcp.py:37-58` |
| M-03 | **Medium** | Requirements | Transparency | No model card for AI-powered features | `cli/prompt.py` |
| M-04 | **Medium** | Design | Fairness & Bias | No fairness evaluation support in evals framework | `experimental/api_client.py` |
| M-05 | **Medium** | Design | Human Oversight | No human-in-the-loop or escalation mechanism | Architecture-level |
| M-06 | **Medium** | Requirements | Transparency | `logfire prompt` has no model disclosure | `cli/prompt.py` |
| L-01 | **Low** | Requirements | Regulatory Gap | EU AI Act risk classification absent | Architecture-level |
| L-02 | **Low** | Verification | ML Supply Chain | No model version fingerprinting | `semconv.py` |
| L-03 | **Low** | Design | Human Oversight | No anomaly detection hooks | Architecture-level |
| L-04 | **Low** | Requirements | Regulatory Gap | GDPR Art. 22 documentation gap | Architecture-level |

---

## 15. Recommendations Roadmap

### Immediate (Critical — address before next release)

1. **[C-01]** Remove or document the `logfire.openai` / `logfire.anthropic` scrubbing bypass in `scrubbing.py`. If intentional, add a `scrub_llm_content` option.
2. **[C-02]** Add `capture_input: bool = True` and `capture_output: bool = True` to `instrument_openai()` and `instrument_anthropic()`.
3. **[H-01]** Remove `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`, `pydantic_ai.all_messages` from `SAFE_KEYS` or make them conditionally safe.

### Short-term (High — within 1–2 releases)

4. **[H-02]** Add `capture_images: bool = False` / `capture_audio: bool = False` to OpenAI and Anthropic instrumentation, defaulting to off.
5. **[H-03]** Document that no content safety filtering is applied and provide patterns for integrating safety callbacks.
6. **[H-04]** Apply upper-bound version constraints to `openinference-instrumentation-litellm` and `openinference-instrumentation-dspy`.

### Medium-term (Medium — within next quarter)

7. **[M-01]** Add `LOGFIRE_CAPTURE_LLM_CONTENT=false` environment variable as a global master switch.
8. **[M-02]** Apply `capture_input`/`capture_output` controls to `instrument_mcp()`.
9. **[M-03]** Create model cards / system cards for all AI-powered features.
10. **[M-04]** Add demographic metadata support to the evals framework; document fairness evaluation patterns.
11. **[M-05]** Document human-in-the-loop patterns using existing Logfire APIs.
12. **[M-06]** Add AI model disclosure to `logfire prompt` output.

### Long-term (Low — ongoing)

13. **[L-01]** Conduct EU AI Act risk classification exercise.
14. **[L-02]** Extract `system_fingerprint` from OpenAI responses.
15. **[L-03]** Document anomaly detection patterns using Logfire metrics.
16. **[L-04]** Add GDPR Art. 22 compliance guidance to documentation.

---

*This report was produced by static analysis of the `logfire` v4.31.0 source code. It does not constitute legal advice. Regulatory compliance determinations should involve qualified legal counsel familiar with applicable jurisdictions. The closed-source Logfire SaaS platform (server, dashboard, data storage) is out of scope and requires a separate assessment by the platform team.*
