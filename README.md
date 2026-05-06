# Agentic Resume Optimizer & Builder

Comprehensive, evidence-first resume optimizer and builder that minimizes LLM hallucinations while producing ATS-friendly, exportable resumes. This README is intentionally detailed for developers, recruiters, and maintainers.

Core goals:
- Produce resumes grounded in verifiable evidence (GitHub, uploaded resume, user answers).
- Preserve metrics and avoid inventing claims.
- Keep matching, scoring and validation deterministic and explainable.
- Use LLMs only for structured language tasks (parsing, structured generation, clarifying questions).
---

## Elevator pitch
Create trustworthy, export-ready resumes that keep candidate claims honest and help recruiters and hiring teams evaluate evidence quickly.

---

## Top features
- Evidence-backed outputs: extracts facts from README files, repo metadata, and uploaded resumes.
- Hallucination gate: LLM-proposed claims are validated and blocked from export when unsupported.
- Metric preservation: numeric metrics are detected and preserved from source evidence.
- Deterministic skill matching: multi-tier logic (exact, stem/overlap, fuzzy, acronym, alias).
- Compact event trace: small JSON step logs for auditing and debugging.
- Multiple exports: Markdown, DOCX, PDF and TXT.

---

## Very short architecture summary
The codebase is organized into clear responsibilities. Major files:

- `app.py` — Streamlit entry, mode selector and top-level UI.
- `builder_app.py` — Builder-specific UI and human-question flow.
- `pipeline.py` — Optimizer workflow for existing resume + JD.
- `builder_pipeline.py` — GitHub-based profile builder workflow.
- `model_client.py` — LLM client wrapper with JSON repair and retries.
- `optimizer_llm.py` / `builder_llm.py` — Focused LLM prompt templates returning structured JSON.
- `resume_format.py` — Schema, data normalization, and render-to-text helpers.
- `matcher.py` — Deterministic matching and ATS scoring functions.
- `validator.py` — Claim validation, metric checks and quality gating.
- `exporter.py` — Export helpers (MD, DOCX, PDF, TXT).

---

## Detailed workflows

Optimizer (existing resume) — step-by-step:

1. Input: resume file (PDF/DOCX/TXT), full job description, target role.
2. `pipeline.py` parses the resume and JD (LLM) into structured JSON.
3. `matcher.py` applies deterministic matching and computes ATS score.
4. `optimizer_llm.py` rewrites resume sections using structured prompts.
5. `validator.py` checks each generated claim for evidence and metrics.
6. If validator passes, `exporter.py` writes the final file; otherwise the system offers a targeted `repair` pass.

Builder (from GitHub) — step-by-step:

1. Input: GitHub profile URL (and optional LinkedIn export, old resume, portfolio).
2. `builder_pipeline.py` fetches profile and public repos (`github_tools.py`).
3. For top N repos (default N=8) it fetches README and runs `analyze_repo_with_llm()` to extract features, evidence and strengths.
4. Generates missing questions (`generate_missing_questions`) if human clarification is needed.
5. Builds unified `candidate_profile` from GitHub + user answers + old resume.
6. Ranks projects, converts top projects to structured resume JSON (`resume_format.py` + LLM), validates claims, and exports if safe.

---

## Skill matching (details)

Matching is deterministic and multi-step to be explainable:

1. Exact token match (case-insensitive, variant-aware).
2. Token stem/overlap using light normalization.
3. Fuzzy string similarity threshold (SequenceMatcher, default 0.82).
4. Acronym expansion (derived heuristics for common acronyms).
5. Alias/lookup list (domain-specific mapping for common synonyms such as `FAISS` → `vector database`).

All match decisions are logged in the event trace with reasons.

---

## Validation & safety

Validators run deterministic checks:
- Hallucination detection: confirm generated claims against `candidate_profile`, `repo_analysis`, and `old_resume_text`.
- Metric preservation: regex-based extraction of numeric metrics from inputs and generated text.
- Quality gate: length checks, weak-phrase detection, and ATS score threshold enforcement (configurable).

Export only occurs when blocking validators pass; otherwise output is marked `draft_needs_review` and repair suggestions are surfaced.

---

## Developer setup (detailed)

1. Clone and install:

```bash
git clone https://github.com/harshitttiwari/Resume-OPT.git
cd Resume-OPT
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt
```

2. Environment variables (`.env` recommended):

```env
GEMINI_API_KEY=...
GROQ_API_KEY=...
GITHUB_TOKEN=...   # optional, for private repo access or higher rate limits
LLM_PROVIDER=auto
```

3. Run the Streamlit app locally:

```bash
streamlit run app.py
```

---

## Example: quick run (optimizer mode)

1. Open the UI and choose "Optimize Existing Resume".
2. Upload a resume file and paste the full job description.
3. Click `Optimize Resume`.

Result: the UI shows ATS score breakdown, matched/missing skills, claim validation results, and export options.

---

## Testing

There are no formal unit tests in the repo currently. Suggested quick checks:

1. Run `python -c "from resume_format import write_resume_from_profile; print('ok')"` to verify imports.
2. Use sample JSON inputs (in `cache/`) to simulate the builder flow and inspect `resume_text`.

I can add a small `tests/` harness if you want automated checks.

---

## Deployment and costs

- LLM usage should be minimized: structured prompts and caching are used to limit repeated calls.
- For production, run the Streamlit app behind a simple web server and set up secure storage for API keys.

---

## Design notes and tradeoffs

- No embeddings: avoids extra infra and keeps matching deterministic and explainable, at the cost of some semantic nuance.
- LLMs used only for parsing and structured generation: minimizes hallucination surface.
- Compact event trace instead of chain-of-thought: reduces token usage and avoids exposing chain-of-thought to outputs.

---

## Contributing

PRs welcome. Preferred changes:
- Add tests for any core matcher/validator behavior.
- Keep LLM prompts structured and avoid asking for chain-of-thought in prompts.

---

## Contact & Demo

- Open an issue or PR on GitHub for questions. I can prepare a short demo script or a 2–3 slide walkthrough on request.

---

*This README is intentionally detailed for maintainers and recruiters while keeping security and reproducibility in mind.*

---

## Architecture (short)

- `app.py`: Streamlit entry point and mode selector.
- `pipeline.py`: Optimizer workflow for existing resumes.
- `builder_pipeline.py`: GitHub-based builder workflow.
- `builder_app.py`: Streamlit UI for builder flow.
- `model_client.py`: JSON-safe LLM client, retries and repair.
- `*_llm.py`: Focused prompts producing structured JSON.
- `resume_format.py`: JSON schema, deterministic cleanup, and renderer.
- `matcher.py`: Deterministic skill matching + ATS scoring.
- `validator.py`: Truth, metric and quality checks that gate export.
- `exporter.py`: Simple file exports (MD/DOCX/PDF/TXT).

All LLM calls use structured JSON I/O and caching to limit token usage. Deterministic logic handles scoring and gating.

---

## How it works (brief workflows)

Optimizer flow (existing resume):
1. Parse resume and JD → create structured JSON (LLM)
2. Deterministic skill matching & ATS scoring
3. LLM rewrites resume using structured prompts
4. Validator checks (hallucination, metrics, quality)
5. Export if safe, else ask for repair/human review

Builder flow (from GitHub):
1. Fetch GitHub profile and top repos
2. Analyze READMEs and extract evidence
3. Generate missing questions for candidate input (if needed)
4. Build candidate profile and rank projects
5. Produce structured resume JSON (LLM) and render
6. Validate claims → export if safe

---

## Practical benefits for hiring teams
- Faster triage: evidence-backed bullets make it easier to evaluate candidate claims.
- Lower risk: blocked hallucinations reduce false positives in screening.
- Audit trail: event traces show why a claim was accepted or rejected.

---

## Quick start
```bash
git clone https://github.com/harshitttiwari/Resume-OPT
cd Resume-OPT
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Set API keys in `.env` or environment variables (LLM keys and `GITHUB_TOKEN` if you want repo access).

Run the app:
```bash
streamlit run app.py
```

---

If you want, I can produce a 2–3 slide demo for recruiters showing the optimizer and builder flows with screenshots.

---

Contact: open an issue or PR on the repo, or message via the GitHub profile.

*This README is written to help recruiters and hiring managers quickly understand the project value, architecture, and how to run it.*
