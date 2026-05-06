"""Compatibility layer for LLM helper functions.

The project imports from this file in a few places.  To keep those imports stable
and beginner-friendly, the real code is split into small modules:
- model_client.py: Gemini/Groq JSON calls
- optimizer_llm.py: old resume optimizer prompts
- builder_llm.py: GitHub builder prompts
- resume_format.py: structured resume schema and rendering
"""

from model_client import ask_json, invoke_llm, parse_json, _selected_provider
from optimizer_llm import (
    analyze_jd_with_llm,
    parse_resume_with_llm,
    rewrite_resume_with_llm,
    truth_check_with_llm,
)
from builder_llm import (
    analyze_repo_with_llm,
    build_candidate_profile,
    generate_missing_questions,
    validate_resume_claims,
    write_resume_from_profile,
)
from resume_format import (
    build_structured_resume_json,
    finalize_resume_structure,
    normalize_structured_resume,
    render_structured_resume,
)

__all__ = [
    "ask_json",
    "invoke_llm",
    "parse_json",
    "_selected_provider",
    "analyze_jd_with_llm",
    "parse_resume_with_llm",
    "rewrite_resume_with_llm",
    "truth_check_with_llm",
    "analyze_repo_with_llm",
    "build_candidate_profile",
    "generate_missing_questions",
    "validate_resume_claims",
    "write_resume_from_profile",
    "build_structured_resume_json",
    "finalize_resume_structure",
    "normalize_structured_resume",
    "render_structured_resume",
]
