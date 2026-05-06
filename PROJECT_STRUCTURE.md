# Project Structure

This project has two resume workflows:

1. Optimize an existing resume for a job description.
2. Build a resume from GitHub, safe LinkedIn input, old resume evidence, and user answers.

## Main App Files

- `app.py`: Streamlit entry point and mode selector.
- `builder_app.py`: Streamlit UI for the GitHub resume builder.

## Workflow Files

- `pipeline.py`: Existing resume optimizer workflow.
- `builder_pipeline.py`: GitHub builder workflow with compact `event_trace`.
- `workflow.ipynb`: Current workflow documentation notebook.

## LLM Files

- `model_client.py`: Gemini/Groq JSON calls, provider selection, fallback, and JSON repair.
- `optimizer_llm.py`: Prompts for the existing resume optimizer.
- `builder_llm.py`: Prompts for the GitHub resume builder.
- `resume_format.py`: Resume JSON schema, cleanup rules, project inclusion, achievement filtering, and rendering.
- `llm.py`: Small compatibility wrapper so older imports still work.

## Supporting Files

- `github_tools.py`: GitHub API, README cache, username extraction, and safe LinkedIn ZIP parsing.
- `parser.py`: Loads PDF/DOCX/TXT resumes and normalizes parsed resume/JD data.
- `matcher.py`: Deterministic skill matching and ATS scoring.
- `validator.py`: Truth, metric, and quality checks.
- `exporter.py`: Exports Markdown, TXT, DOCX, and PDF.
- `log.py`: Shared logger.

## Data Folders

- `cache/`: GitHub profile, repo, and README cache.
- `sessions/`: Saved builder sessions as JSON.
- `outputs/`: Generated resume files.

