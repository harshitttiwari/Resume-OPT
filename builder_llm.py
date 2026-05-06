"""LLM prompts used by the GitHub resume builder flow."""

from __future__ import annotations

import json
from typing import Any

from model_client import ask_json
from resume_format import write_resume_from_profile

# GitHub repo analysis for builder

def analyze_repo_with_llm(repo: dict[str, Any], readme: str, target_role: str) -> dict[str, Any]:
    prompt = f"""
Analyze this GitHub repository for a candidate applying for: {target_role}

Return only valid JSON:
{{
  "project_name": "",
  "problem": "",
  "tech_stack": [],
  "features": [],
  "evidence": [],
  "resume_strength": 0,
  "recommended_for_roles": []
}}

Rules:
- resume_strength must be 1-10.
- evidence must be facts from repo description or README only.
- Do not invent features not mentioned in README or description.
- features must describe what the project does or technically implements.
- Never include meta-descriptions like "clean architecture" or "no hardcoding".

Repo name: {repo.get("name", "")}
Description: {repo.get("description", "")}
Language: {repo.get("language", "")}
Topics: {repo.get("topics", [])}
Stars: {repo.get("stars", 0)}

README:
{readme[:4000]}
"""
    try:
        return ask_json(prompt, fast=True)
    except Exception:
        return {
            "project_name": repo.get("name", ""),
            "problem": repo.get("description", ""),
            "tech_stack": [repo.get("language", "")] if repo.get("language") else [],
            "features": [],
            "evidence": [],
            "resume_strength": 1,
            "recommended_for_roles": [],
        }


# Missing questions

def generate_missing_questions(
    candidate_profile: dict[str, Any],
    target_role: str,
) -> dict[str, Any]:
    prompt = f"""
A candidate wants to build a resume for: {target_role}

Based on available data, generate only important missing questions.

Return only valid JSON:
{{
  "questions": ["question 1", "question 2"]
}}

Rules:
- Ask at most 6 questions.
- Ask only what is necessary to create a truthful resume.
- Do not ask for information already visible in GitHub, old resume, LinkedIn export, or known data.
- Focus on missing education, internships, certifications, achievements, metrics, project contribution, and target-role preference.
- Ask for metrics only when useful and no metric is available.
- Keep questions short and easy for a student to answer.

Known data:
{json.dumps(candidate_profile, ensure_ascii=False)[:5000]}
"""
    try:
        return ask_json(prompt, fast=True)
    except Exception:
        return {
            "questions": [
                "What is your highest qualification and institution name?",
                "Do you have internships, training, or work experience to include?",
                "Which certifications should be included?",
                "Which achievements or awards should be included?",
            ],
        }


# Candidate profile builder

def build_candidate_profile(
    github_profile: dict,
    repo_analysis: list,
    old_resume: str,
    user_answers: dict,
    target_role: str,
) -> dict[str, Any]:
    prompt = f"""
Build a structured candidate profile from the sources below.

Return only valid JSON:
{{
  "name": "",
  "email": "",
  "phone": "",
  "linkedin_url": "",
  "github_url": "",
  "portfolio_url": "",
  "target_role": "",
  "education": [
    {{
      "degree": "",
      "institution": "",
      "year": "",
      "cgpa": "",
      "evidence_source": ""
    }}
  ],
  "skills": [],
  "certifications": [],
  "experience": [
    {{
      "company": "",
      "role": "",
      "duration": "",
      "type": "internship/virtual/hackathon/research/work",
      "bullet_points": []
    }}
  ],
  "projects": [],
  "achievements": []
}}

Rules:
- Use only GitHub profile, repo analysis, old resume, LinkedIn export, and user answers.
- Do not invent facts.
- Preserve education details exactly from old resume or user answers.
- If CGPA/grade is present in old resume or user answers, keep it and mark evidence_source.
- For experience, write 2-4 bullets only when evidence is available.
- If experience evidence is weak, keep it concise instead of inventing details.
- Extract skills only from available evidence.

Target role: {target_role}

GitHub profile:
{json.dumps(github_profile, ensure_ascii=False)[:2500]}

LinkedIn exported data:
{json.dumps(user_answers.get("linkedin_data", {}), ensure_ascii=False)[:2500]}

Repo analysis:
{json.dumps(repo_analysis[:8], ensure_ascii=False)[:5000]}

Old resume text:
{old_resume[:5000]}

User answers:
{json.dumps(user_answers, ensure_ascii=False)[:3000]}
"""
    return ask_json(prompt)

# Claim validation for builder

def validate_resume_claims(
    resume_text: str,
    candidate_profile: dict,
    repo_analysis: list,
    old_resume_text: str = "",
    user_answers: dict | None = None,
) -> dict[str, Any]:
    prompt = f"""
Validate every claim in the resume against the evidence sources.

Return only valid JSON:
{{
  "safe_claims": [],
  "needs_confirmation": [],
  "unsafe_claims": [],
  "is_safe": true
}}

Rules:
- safe_claims: supported by GitHub, old resume, LinkedIn export, or user answers.
- needs_confirmation: plausible but not directly evidenced.
- unsafe_claims: cannot be traced to any source.
- is_safe is true only if unsafe_claims is empty.
- Do not mark a claim safe just because it sounds likely.
- Do not punish general wording if the underlying fact is supported.
- Be strict with metrics, certifications, deployment claims, companies, and rankings.

Resume:
{resume_text[:7000]}

Evidence sources:
Profile:
{json.dumps(candidate_profile, ensure_ascii=False)[:5000]}

Projects:
{json.dumps(repo_analysis[:8], ensure_ascii=False)[:6000]}

Old resume text:
{old_resume_text[:5000]}

User answers:
{json.dumps(user_answers or {}, ensure_ascii=False)[:3000]}
"""
    try:
        return ask_json(prompt)
    except Exception as exc:
        return {
            "safe_claims": [],
            "needs_confirmation": [],
            "unsafe_claims": [f"Validation failed: {exc}"],
            "is_safe": False,
        }
