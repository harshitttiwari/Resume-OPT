# Agentic Resume Optimizer & Builder

A compact, safety-first final-year project for optimizing an existing resume or building a resume from GitHub evidence. It uses Streamlit, deterministic Python checks, and Gemini/Groq LLM calls only where language understanding is needed.

---

## What Problem Does This Solve

Most resume tools either blindly rewrite with an LLM (hallucination risk) or do simple keyword stuffing (no intelligence). This project solves both:

- **Hallucination problem** — truth check catches invented claims before export
- **Metric loss problem** — regex-based metric preservation catches dropped numbers
- **Overfit problem** — works across AI/ML, finance, business, marketing, design resumes
- **Black box problem** — every match, score, and validation decision is explainable

---

## What Makes It Different

| Feature | This Project | Typical Resume Tools |
|---|---|---|
| LLM used only where needed | ✅ | ❌ LLM for everything |
| Deterministic skill matching | ✅ | ❌ Embedding-based only |
| Hallucination gate before export | ✅ | ❌ |
| Metric preservation validation | ✅ | ❌ |
| Repair pass with targeted feedback | ✅ | ❌ |
| LangGraph agentic workflow | ✅ | ❌ |
| Structured JSON I/O for all LLM calls | ✅ | ❌ |
| No domain-specific hardcoding | ✅ | ❌ |

---

## Architecture

```
app.py              -> Streamlit mode selector
builder_app.py      -> Streamlit UI for GitHub resume builder
pipeline.py         -> Existing resume optimizer workflow
builder_pipeline.py -> GitHub builder workflow with compact event_trace
model_client.py     -> Gemini/Groq client, JSON parsing, JSON repair
optimizer_llm.py    -> LLM prompts for optimizer mode
builder_llm.py      -> LLM prompts for builder mode
resume_format.py    -> Resume JSON schema, cleanup, rendering
llm.py              -> Small compatibility import wrapper
parser.py           -> File loading and resume/JD parsing helpers
matcher.py          -> Deterministic skill matching and ATS scoring
validator.py        -> Truth, metric, and quality checks
exporter.py         -> MD, DOCX, PDF, TXT export
workflow.ipynb      -> Current workflow documentation notebook
```

---

## Workflow

```
Optimizer:
load_validate -> parse_analyze -> match_score -> rewrite -> validate
validate -> repair -> validate -> export
validate -> export

Builder:
input -> source_check -> github_fetch -> readme_analysis -> linkedin_safe
-> resume_parse -> question_generation -> human_answers -> profile_build
-> project_ranking -> resume_write -> claim_validation -> human_review -> export
```

**Optimizer nodes:**

| Node | Responsibility |
|---|---|
| `load_validate` | Load PDF/DOCX/TXT, validate inputs |
| `parse_analyze` | LLM parses resume + analyzes JD into structured JSON |
| `match_score` | Deterministic skill matching, baseline ATS score |
| `rewrite` | LLM rewrites resume with structured JSON prompt |
| `validate` | Truth check, metric check, quality check |
| `repair` | One targeted repair pass if validation fails |
| `export` | Exports only if all safety checks pass |

**Conditional routing:** after `validate`, the graph decides autonomously — repair or export. `repair_done` flag prevents infinite loops.

---

## How Skill Matching Works

No embeddings. No ML models for matching. Pure deterministic Python:

1. **Exact match** — direct term or variant found in resume text
2. **Token stem overlap** — stemmed tokens of skill match stemmed tokens in evidence units
3. **Fuzzy ratio** — `SequenceMatcher` at ≥ 0.82 threshold
4. **Acronym matching** — `ML` matches `Machine Learning`, `FastAPI` matches via embedded acronym
5. **Semantic aliases** — `vector databases` matches if `ChromaDB`, `Pinecone`, or `FAISS` is present

All five tiers are explainable in an interview without referencing any model.

---

## ATS Score Formula

```
ATS = (matched/total × 50) + (required_matched/required_total × 35) + (evidence_quality × 15) − penalty
```

- **50%** — overall keyword coverage
- **35%** — required skills coverage (weighted higher)
- **15%** — evidence quality (how strongly each skill appears)
- **Penalty** — up to −10 for missing required skills

---

## Safety Checks

| Check | Method | Blocks Export |
|---|---|---|
| Hallucination detection | LLM truth check + false-positive filter | ✅ |
| Metric preservation | Regex extraction + key comparison | ✅ |
| Quality gate | Length, weak phrases, ATS threshold | ✅ |
| Added summary removal | Line-scan heading detection | No (silent fix) |

Export only happens when all three blocking checks pass. Otherwise output is marked `draft_needs_review`.

---

## Models Used

| Task | Model | Reason |
|---|---|---|
| Final resume writing | `gemini-2.5-flash` or Groq strong model | Quality matters most here |
| Repo analysis, parsing, questions, validation | `gemini-2.5-flash-lite` or Groq fast model | Repeated calls need speed and token efficiency |

LLM calls are cached with `lru_cache` — repeated identical inputs do not cost tokens.

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| Orchestration | LangGraph for optimizer, simple two-phase Python runner for builder |
| LLM | Gemini or Groq |
| LLM Client | `requests` for Gemini, LangChain-Groq for Groq |
| PDF parsing | PyMuPDF (fitz) |
| DOCX parsing/export | python-docx |
| PDF export | ReportLab |
| Environment | python-dotenv |

---

## Quick Start

**1. Clone and set up environment**
```bash
git clone <repo-url>
cd agentic-resume-optimizer
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**2. Configure environment variables**
```env
LLM_PROVIDER=auto
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
GITHUB_TOKEN=your_github_token_here
GEMINI_FAST_MODELS=gemini-2.5-flash-lite,gemini-2.5-flash
GEMINI_STRONG_MODELS=gemini-2.5-flash,gemini-2.5-flash-lite
```

**3. Run the app**
```bash
streamlit run app.py
```

**4. (Optional) View workflow notebook**
```bash
jupyter notebook workflow.ipynb
```
The notebook documents the current optimizer and builder workflows.

---

## How To Use

1. Upload a resume — PDF, DOCX, or TXT
2. Paste the full job description
3. Enter the target role
4. Choose export format — DOCX, PDF, or TXT
5. Click **Optimize Resume**
6. Review ATS score, matched/missing skills, truth check, metric preservation
7. Download export if it passed all safety checks

---

## Project Structure

```
Resume/
├── app.py                 # Streamlit entry point
├── builder_app.py         # Builder UI
├── pipeline.py            # Optimizer workflow
├── builder_pipeline.py    # Builder workflow
├── model_client.py        # Gemini/Groq client
├── optimizer_llm.py       # Optimizer prompts
├── builder_llm.py         # Builder prompts
├── resume_format.py       # Resume schema and rendering
├── llm.py                 # Compatibility wrapper
├── parser.py              # Resume/JD parsing helpers
├── matcher.py             # Skill matching + ATS scoring
├── validator.py           # Safety checks
├── exporter.py            # File export
├── workflow.ipynb         # Workflow documentation
├── requirements.txt
└── .env                   # API keys
```

---

## Design Decisions

**LLM only for language tasks** — parsing, rewriting, truth checking. Scoring, matching, metric validation, and export gating are all deterministic Python. Cheaper, faster, fully debuggable.

**Structured JSON I/O** — every LLM call sends structured JSON input and expects JSON output. Reduces hallucination surface and makes outputs parseable without fragile string cleaning.

**One repair pass maximum** — if the first rewrite regresses on metrics or ATS coverage, the graph routes to repair with explicit targeted feedback. No infinite loops.

**No embedding models** — skill matching uses token stemming, variant generation, fuzzy ratio, and semantic aliases. Keeps dependencies minimal and matching logic fully explainable.

**Export gate** — a low ATS score does not block export. Only hallucinations, missing metrics, and quality failures block it. A weak match is honest information, not a system failure.
