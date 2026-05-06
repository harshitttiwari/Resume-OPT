# Agentic Resume Optimizer & Builder

This project helps turn a resume, job description, or GitHub profile into a better resume. It is designed to be simple to understand, safe, and useful for real life use.

The project has two modes:

- Optimize an existing resume for a job description.
- Build a resume from GitHub evidence and optional extra inputs.

The main idea is simple: use Python for the logic, and use the LLM only where language understanding is needed.

## What the project does

- Reads a resume and job description.
- Compares the resume with the job requirements.
- Finds missing or matched skills.
- Rewrites the resume in a cleaner ATS-friendly format.
- Checks for unsupported claims before export.
- Builds a new resume from GitHub repositories, README files, and optional LinkedIn export or old resume.

## Why this project is useful

- It is more honest than a fully automatic LLM resume writer.
- It keeps important numbers and metrics when they are present in evidence.
- It works across many domains like software, AI/ML, business, marketing, design, and analytics.
- It is explainable, so a recruiter or reviewer can understand what happened.

## Simple architecture

- `app.py` — main Streamlit app.
- `pipeline.py` — optimize existing resume flow.
- `builder_app.py` — Streamlit UI for the builder flow.
- `builder_pipeline.py` — GitHub-based resume builder flow.
- `model_client.py` — talks to the LLM and handles JSON repair.
- `matcher.py` — skill matching and ATS score.
- `validator.py` — truth and quality checks.
- `resume_format.py` — structured resume JSON and rendering.
- `exporter.py` — export to MD, DOCX, PDF, and TXT.

## Main workflow

Optimizer mode:

1. Upload resume.
2. Paste the job description.
3. Parse the resume and JD.
4. Match skills and score the resume.
5. Rewrite the resume.
6. Validate the result.
7. Export the final file.

Builder mode:

1. Enter GitHub URL.
2. Fetch profile and repositories.
3. Read README files and analyze projects.
4. Ask for missing information if needed.
5. Build a candidate profile.
6. Rank the best projects.
7. Generate the resume and validate it.
8. Export the final file.

## Basic tech details

- Streamlit for the user interface.
- LangGraph for workflow control.
- Python for matching, validation, and export.
- LLM calls only for text understanding and structured resume generation.

## How to run it

```bash
git clone https://github.com/harshitttiwari/Resume-OPT.git
cd Resume-OPT
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Good to know

- The project uses compact event logs instead of long agent thoughts.
- It does not scrape LinkedIn.
- It keeps the code simple and avoids unnecessary over-engineering.
