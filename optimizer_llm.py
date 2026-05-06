"""LLM prompts used by the old resume optimizer flow."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from model_client import ask_json

# Resume parsing for old optimizer

@lru_cache(maxsize=16)
def parse_resume_with_llm(resume_text: str) -> dict[str, Any]:
    prompt = f"""
Return only valid JSON for this resume.
Use empty strings or empty lists when a field is absent.
Do not invent or infer information not explicitly written in the resume.

Schema:
{{
  "name": "",
  "email": "",
  "phone": "",
  "skills": [],
  "projects": [
    {{"title": "", "description": "", "tech_stack": [], "impact": ""}}
  ],
  "experience": [
    {{"company": "", "role": "", "duration": "", "bullet_points": []}}
  ],
  "education": [
    {{"degree": "", "institution": "", "year": ""}}
  ],
  "certifications": []
}}

Resume:
{resume_text[:12000]}
"""
    return ask_json(prompt, fast=True)


# JD analysis for old optimizer

@lru_cache(maxsize=16)
def analyze_jd_with_llm(job_description: str) -> dict[str, Any]:
    prompt = f"""
Extract job requirements as valid JSON only.

Rules:
- Include only skills, tools, and keywords explicitly written in the job description.
- Do not add skills that are implied but not written.
- Split compound terms: "reporting and analysis" -> ["reporting", "analysis"].
- Deduplicate case variants: "Python" and "python" -> one entry.

Schema:
{{
  "job_title": "",
  "required_skills": [],
  "preferred_skills": [],
  "tools": [],
  "keywords": [],
  "notes": ""
}}

Job description:
{job_description[:12000]}
"""
    return ask_json(prompt, fast=True)


# Old optimizer resume rewriting

def rewrite_resume_with_llm(context: dict[str, Any]) -> str:
    """
    Used by the original resume optimizer flow:
    existing resume + JD -> rewritten resume.
    """
    repair_section = ""

    if context.get("current_draft"):
        repair_section = f"""
This is a repair pass. Improve the draft below using the feedback.
Do not start from scratch.

Current draft:
{context["current_draft"][:12000]}

Repair feedback:
{context.get("rewrite_feedback", "")}
"""

    prompt = f"""
You are rewriting a resume to better match a target role.

Return only valid JSON:
{{"resume_text": "<full rewritten resume as a single string>"}}

Strict rules:
- Use only facts from the original resume.
- Do not invent employers, projects, degrees, tools, certifications, metrics, or outcomes.
- Preserve every number, percentage, date, score, latency, URL, version, and named tool exactly as written.
- Keep all original projects, experience entries, and bullets unless they are exact duplicates.
- Do not collapse multiple bullets into one vague bullet.
- Use stronger action verbs only where the original fact supports it.
- Do not claim skills from missing_skills unless the original resume already demonstrates them.
- Do not add a career summary/objective unless one exists in the original resume.

Input context:
{json.dumps({
    "target_role": context["target_role"],
    "matched_skills": context["matched_skills"],
    "missing_skills": context["missing_skills"],
    "must_keep_metrics": context.get("must_keep_metrics", []),
    "jd_analysis": context["jd_analysis"],
    "parsed_resume": context["parsed_resume"],
}, ensure_ascii=False)}

{repair_section}

Original resume:
{context["raw_resume_text"][:12000]}
"""
    result = ask_json(prompt)
    resume_text = result.get("resume_text", "")

    if not resume_text:
        raise ValueError("LLM returned empty resume_text in rewrite response.")

    return resume_text


# Truth checking for old optimizer

def truth_check_with_llm(original_text: str, rewritten_text: str) -> dict[str, Any]:
    prompt = f"""
Check whether the rewritten resume contains facts not supported by the original.
Ignore formatting, grammar, word order, and stronger phrasing when the fact is supported.

Return JSON only:
{{"is_truthful": true, "issues": []}}

Original resume:
{original_text[:9000]}

Rewritten resume:
{rewritten_text[:9000]}
"""
    try:
        data = ask_json(prompt, fast=True)
        return {
            "is_truthful": bool(data.get("is_truthful")),
            "issues": [str(x) for x in data.get("issues", [])],
        }
    except Exception as exc:
        return {
            "is_truthful": False,
            "issues": [f"Truth check failed: {exc}"],
        }
