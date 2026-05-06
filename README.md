# Agentic Resume Optimizer & Builder — recruiter-focused README

This project produces evidence-backed, ATS-friendly resumes by combining deterministic Python logic with focused LLM calls only where natural language understanding is required. It supports two main flows:

- Optimize an existing resume for a target job (parse, match, rewrite, validate).
- Build a resume from public GitHub evidence (fetch repos, analyze READMEs, generate profile, build resume).

Why this matters to recruiters and hiring managers:
- Evidence-first: claims are verified against real artifacts (GitHub README, old resume, user answers).
- Reduced hallucination risk: validators block unsupported claims from reaching the final export.
- ATS-ready output: deterministic matching and an ATS scoring formula produce predictable results.
- Explainability: compact event traces and deterministic rules make decisions auditable.

---

## Elevator pitch
Create trustworthy, export-ready resumes that keep candidate claims honest and help recruiters evaluate evidence quickly.

---

## Top features
- Evidence-backed outputs (GitHub + resume + user answers)
- Hallucination and metric-preservation checks (blocks unsupported claims)
- Deterministic, explainable skill-matching (no embeddings required)
- Compact event trace for auditing decisions
- Exports to Markdown, DOCX, PDF, and TXT

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
