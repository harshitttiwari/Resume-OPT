"""Input loading, validation, and LLM-backed parsing."""

from __future__ import annotations

import os
import re
from typing import Any

import fitz
from docx import Document

from llm import analyze_jd_with_llm, parse_resume_with_llm


# Text utilities

def clean_text(text: str) -> str:
    text = str(text or "").replace("\x00", " ")
    text = re.sub(r"[•●▪]", "-", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _items(value: Any) -> list[str]:
    """Coerce a value to a flat list of non-empty strings."""
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _dedupe(items: list[str]) -> list[str]:
    """Remove duplicates, case-insensitively, preserving original casing."""
    seen, out = set(), []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out


# File loading

def load_resume_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        with fitz.open(path) as doc:
            return clean_text("\n".join(page.get_text() for page in doc))
    if ext == ".docx":
        doc = Document(path)
        return clean_text("\n".join(p.text for p in doc.paragraphs if p.text.strip()))
    if ext == ".txt":
        with open(path, encoding="utf-8") as fh:
            return clean_text(fh.read())
    raise ValueError("Unsupported resume format. Use PDF, DOCX, or TXT.")


# Input validation

def validate_inputs(
    resume: str, jd: str, role: str, export_format: str
) -> tuple[str, str, str, str]:
    resume = clean_text(resume)
    jd = clean_text(jd)
    role = clean_text(role)
    export_format = str(export_format or "docx").lower().strip()

    if len(resume) < 100:
        raise ValueError("Resume text is too short to analyze.")
    if len(jd) < 50:
        raise ValueError("Job description is too short to analyze.")
    if not role:
        raise ValueError("Target role is required.")
    if export_format not in {"docx", "pdf", "txt"}:
        raise ValueError("Export format must be docx, pdf, or txt.")
    return resume, jd, role, export_format


# LLM output normalization

def _normalize_resume(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize raw LLM parse output into a stable structure.
    Handles schema drift: alternate key names, unexpected types.
    """
    projects = []
    for p in data.get("projects", []) or []:
        if isinstance(p, dict):
            projects.append({
                "title":       str(p.get("title") or p.get("name") or "").strip(),
                "description": str(p.get("description") or "").strip(),
                "tech_stack":  _dedupe(_items(p.get("tech_stack") or p.get("technologies"))),
                "impact":      str(p.get("impact") or "").strip(),
            })

    experience = []
    for job in data.get("experience", []) or []:
        if isinstance(job, dict):
            experience.append({
                "company":       str(job.get("company") or "").strip(),
                "role":          str(job.get("role") or job.get("title") or "").strip(),
                "duration":      str(job.get("duration") or "").strip(),
                "bullet_points": _items(job.get("bullet_points") or job.get("responsibilities")),
            })

    education = []
    for school in data.get("education", []) or []:
        if isinstance(school, dict):
            education.append({
                "degree":      str(school.get("degree") or "").strip(),
                "institution": str(school.get("institution") or school.get("school") or "").strip(),
                "year":        str(school.get("year") or "").strip(),
            })

    return {
        "name":           str(data.get("name") or "").strip(),
        "email":          str(data.get("email") or "").strip(),
        "phone":          str(data.get("phone") or "").strip(),
        "skills":         _dedupe(_items(data.get("skills"))),
        "projects":       projects,
        "experience":     experience,
        "education":      education,
        "certifications": _dedupe(_items(data.get("certifications"))),
    }


# Public parse API

def parse_resume(resume_text: str) -> dict[str, Any]:
    """Parse resume text into structured data via LLM."""
    return _normalize_resume(parse_resume_with_llm(resume_text))


def analyze_job_description(job_description: str) -> dict[str, Any]:
    """Extract structured requirements from a job description via LLM."""
    data = analyze_jd_with_llm(job_description)
    return {
        "job_title":        str(data.get("job_title") or "").strip(),
        "required_skills":  _dedupe(_items(data.get("required_skills"))),
        "preferred_skills": _dedupe(_items(data.get("preferred_skills"))),
        "tools":            _dedupe(_items(data.get("tools"))),
        "keywords":         _dedupe(_items(data.get("keywords"))),
        "notes":            str(data.get("notes") or "").strip(),
    }
