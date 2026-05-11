"""Structured resume schema and rendering helpers for the builder flow."""
from __future__ import annotations
import json
import re
from typing import Any
from model_client import ask_json

RESUME_SCHEMA = {
    "name": "",
    "contact": {
        "email": "",
        "phone": "",
        "linkedin": "",
        "github": "",
        "portfolio": "",
    },
    "education": [{
        "institution": "",
        "location": "",
        "duration": "",
        "degree": "",
        "score": "",
    }],
    "experience": [{
        "title": "",
        "organization": "",
        "location": "",
        "duration": "",
        "certificate": "",
        "bullets": [""],
    }],
    "projects": [{
        "name": "",
        "github": "",
        "technologies": [""],
        "bullets": [""],
    }],
    "skills": [{
        "category": "",
        "items": [""],
    }],
    "certifications": [""],
    "achievements": [""],
}

# Structured resume schema builder 
def build_structured_resume_json(
    candidate_profile: dict,
    ranked_projects: list,
    target_role: str,
    jd_analysis: dict | None = None,
) -> dict[str, Any]:
    """Creates the user's preferred structured resume JSON.
    This is used by write_resume_from_profile(), then rendered into resume_text
    for the existing Streamlit/export pipeline."""
    
    candidate_evidence = {
        "target_role": target_role,
        "candidate_profile": candidate_profile,
        "top_projects": ranked_projects[:4],
        "jd_analysis": jd_analysis or {},
    }

    prompt = f"""
You are a resume data extraction and resume-building assistant.

Task:
Convert the provided candidate evidence into a clean structured resume JSON.

Important:
- Return ONLY valid JSON.
- Do not include markdown.
- Do not include explanation.
- Do not invent any information.
- Use only information present in the provided evidence.
- If a field is missing, use an empty string or empty list.
- This schema must work for any type of resume: AI/ML, software, fashion design, business, marketing, data analyst, etc.
- Follow this resume pattern exactly: Header, Education, Technical Skills, Experience, Projects, Certifications.
- Do not add a summary section.
- Do not hardcode AI/ML-specific categories; skill categories must come from the candidate evidence.
- Skills should be grouped into short categories such as Programming, Tools, Design, Marketing, Analytics, or domain-specific groups only when supported by evidence.
- Keep project descriptions truthful and evidence-backed.
- Include 3 to 4 projects from top_projects when evidence exists.
- Do not omit a ranked project just because another project is stronger.
- Do not create fake metrics, fake certifications, fake companies, fake rankings, or fake deployment claims.
- Use only projects from top_projects.
- Include at most 4 projects.
- Preserve exact technology names.
- Use numbers only if they are explicitly present in evidence.
- Project bullets should be resume-ready and specific, but only use evidence-backed facts.
- Prefer strong project bullets already present in candidate_profile.projects when they match a top project.
- Keep useful metrics from candidate_profile.projects, old resume evidence, or user answers when tied to that project.
- Do not put project outcomes, accuracy, latency, retrieval, ATS, or feature impact inside achievements.
- Achievements are only awards, hackathon results, ranks, honors, publications, scholarships, or official recognitions.

Return the response strictly in this JSON format:
{{
  "name": "",
  "contact": {{
    "email": "",
    "phone": "",
    "linkedin": "",
    "github": "",
    "portfolio": ""
  }},
  "education": [
    {{
      "institution": "",
      "location": "",
      "duration": "",
      "degree": "",
      "score": ""
    }}
  ],
  "experience": [
    {{
      "title": "",
      "organization": "",
      "location": "",
      "duration": "",
      "certificate": "",
      "bullets": [""]
    }}
  ],
  "projects": [
    {{
      "name": "",
      "github": "",
      "technologies": [""],
      "bullets": [""]
    }}
  ],
  "skills": [
    {{
      "category": "",
      "items": [""]
    }}
  ],
  "certifications": [""],
  "achievements": [""]
}}
Evidence:
{json.dumps(candidate_evidence, ensure_ascii=False)[:9000]}
"""
    
    data = normalize_structured_resume(ask_json(prompt))

    # Prefer explicit contact fields from candidate_profile when LLM left them blank
    contact = data.get("contact", {})
    contact["email"] = contact.get("email") or str(candidate_profile.get("email") or "")
    contact["phone"] = contact.get("phone") or str(candidate_profile.get("phone") or "")
    contact["linkedin"] = contact.get("linkedin") or str(candidate_profile.get("linkedin_url") or "")
    contact["github"] = contact.get("github") or str(candidate_profile.get("github_url") or "")
    contact["portfolio"] = contact.get("portfolio") or str(candidate_profile.get("portfolio_url") or "")
    data["contact"] = contact

    # Deterministic cleanup and merge with ranked projects/profile evidence
    return finalize_resume_structure(data, ranked_projects, candidate_profile)

def _simple_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())

def _project_words(text: str) -> set[str]:
    """extracts meaningful words from project text."""
    stop_words = {
        "and", "the", "for", "with", "using", "based", "powered",
        "project", "system", "application", "analysis",
    }
    return {
        word
        for word in re.findall(r"[a-z0-9]+", str(text or "").lower())
        if len(word) > 2 and word not in stop_words
    }

def _items(value: Any) -> list[str]:
    """normalizes input into a clean list of strings"""
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []

def _trim_bullet(text: str, limit: int = 190) -> str:
    """Trim a bullet keeping it readable and ending cleanly.
    Returns an empty string if nothing meaningful remains.
    """
    text = re.sub(r"\s+", " ", str(text or "")).strip(" -")
    if not text:
        return ""
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rsplit(" ", 1)[0].rstrip(",.;") + "."
    return trimmed

def _dedupe(items: list[str]) -> list[str]:
    """removes duplicate text items while keeping the original order"""
    seen, clean = set(), []
    for item in items:
        key = _simple_key(item)
        if key and key not in seen:
            seen.add(key)
            clean.append(item.strip())
    return clean

def _trim_text(text: str, limit: int = 190) -> str:
    """cleans and shortens text without cutting words"""
    text = re.sub(r"\s+", " ", str(text or "")).strip(" -")
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;") + "."

def _project_name(project: dict) -> str:
    return str(
        project.get("name")
        or project.get("project_name")
        or project.get("repo_name")
        or ""
    ).strip()

def _project_url(project: dict) -> str:
    return str(project.get("github") or project.get("repo_url") or "").strip()

def _tech_items(project: dict) -> list[str]:
    return _items(project.get("technologies") or project.get("tech_stack"))

def _is_strong_bullet(text: Any) -> bool:
    """checks whether a resume bullet point is good enough to keep."""
    t = str(text or "").strip()
    if not t:
        return False
    # numeric evidence often indicates strength
    if re.search(r"\d", t):
        return True
    # require at least 10 words for non-numeric bullets
    if len(t.split()) < 10:
        return False
    first = t.split()[0].lower().strip("-")
    action_verbs = {
        "built", "developed", "implemented", "designed", "created",
        "engineered", "deployed", "optimized", "automated", "improved",
        "reduced", "trained", "architected", "led", "launched",
        "integrated", "maintained", "extended", "wrote", "implemented"}
    return first in action_verbs

def _shared_tech_count(left: dict, right: dict) -> int:
    left_items = {_simple_key(item) for item in _tech_items(left)}
    right_items = {_simple_key(item) for item in _tech_items(right)}
    return sum(
        1
        for left_item in left_items
        if any(
            left_item == right_item
            or left_item in right_item
            or right_item in left_item
            for right_item in right_items
        )
    )

def _same_project(left: dict, right: dict) -> bool:
    left_name = _project_name(left)
    right_name = _project_name(right)
    if not left_name or not right_name:
        return False

    if _simple_key(left_name) == _simple_key(right_name):
        return True

    left_url = _project_url(left)
    right_url = _project_url(right)
    if left_url and right_url and left_url.lower() == right_url.lower():
        return True

    common_words = _project_words(left_name) & _project_words(right_name)
    if len(common_words) >= 2:
        return True

    return len(common_words) >= 1 and _shared_tech_count(left, right) >= 2

def _good_bullets(*sources: Any) -> list[str]:
    bullets = []
    for source in sources:
        for item in _items(source):
            bullet = _trim_bullet(item)
            if bullet and (len(bullet.split()) >=10  or re.search(r"\d", bullet)):
                bullets.append(bullet)
    return _dedupe(bullets)[:4]

def _find_project(projects: list, target: dict) -> dict:
    """searches a list of projects and finds the one that matches a target project."""
    for project in projects:
        if isinstance(project, dict) and _same_project(project, target):
            return project
    return {}

def _project_from_ranked(ranked: dict) -> dict:
    return {
        "name": _project_name(ranked),
        "github": _project_url(ranked),
        "technologies": _tech_items(ranked)[:8],
        "bullets": _good_bullets(
            [ranked.get("problem", "")],
            ranked.get("features", []),
            ranked.get("evidence", []),
        ),
    }

def _clean_project(project: dict, ranked: dict, profile: dict) -> dict:
    """creates one clean project entry by merging project information from multiple sources."""
    bullets = []
    bullets.extend(_good_bullets(profile.get("bullet_points"), profile.get("bullets"), profile.get("description")))
    bullets.extend([b for b in _items(project.get("bullets")) if _is_strong_bullet(b)])
    bullets.extend(_good_bullets(ranked.get("evidence", []), ranked.get("features", []), [ranked.get("problem", "")]))

    technologies = _dedupe(
        _tech_items(project)
        + _tech_items(profile)
        + _tech_items(ranked)
    )[:8]

    github = (
        _project_url(project)
        or _project_url(profile)
        or _project_url(ranked)
    )

    return {
        "name": _project_name(project) or _project_name(ranked),
        "github": github,
        "technologies": technologies,
        "bullets": _dedupe([_trim_bullet(b) for b in bullets if b])[:4],
    }

def _strict_achievements(items: list[str]) -> list[str]:
    achievement_words = {
        "award", "awarded", "winner", "won", "finalist", "rank", "ranked",
        "honor", "honour", "scholarship", "selected", "publication",
        "published", "hackathon", "competition", "medal", "recognition",
    }
    clean = []
    for item in items:
        words = set(re.findall(r"[a-z0-9]+", item.lower()))
        is_real_achievement = bool(words & achievement_words)
        if is_real_achievement:
            clean.append(item)
    return _dedupe(clean)

def finalize_resume_structure(
    data: dict[str, Any],
    ranked_projects: list[dict],
    candidate_profile: dict | None = None,
) -> dict[str, Any]:
    """
    Deterministic cleanup after the LLM response:
    - keep 3-4 evidence-backed ranked projects
    - keep achievements only for awards/honors, not project metrics
    """
    candidate_profile = candidate_profile or {}
    llm_projects = data.get("projects", [])
    profile_projects = candidate_profile.get("projects", [])

    cleaned_projects = []
    for ranked in ranked_projects[:4]:
        project = _find_project(llm_projects, ranked) or _project_from_ranked(ranked)
        profile_project = _find_project(profile_projects, ranked) or _find_project(profile_projects, project)
        cleaned_projects.append(_clean_project(project, ranked, profile_project))

    data["projects"] = cleaned_projects
    data["achievements"] = _strict_achievements(data.get("achievements", []))
    return data

def _clean_location(institution: str, location: str) -> str:
    institution_key = _simple_key(institution)
    location_key = _simple_key(location)
    if location_key and location_key in institution_key:
        return ""
    return location.strip()

def _format_score(score: str) -> str:
    score = str(score or "").strip()
    if not score:
        return ""
    if re.match(r"(?i)^(cgpa|gpa|grade|score|marks)\b", score):
        return score
    if "%" in score:
        return f"Grade: {score}"
    if re.fullmatch(r"\d(?:\.\d+)?(?:/\d(?:\.\d+)?)?", score):
        return f"CGPA: {score}"
    return score

def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []

def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}

def _text(value: Any) -> str:
    return str(value or "").strip()

def _clean_list(value: Any) -> list[str]:
    return [_text(item) for item in _as_list(value) if _text(item)]

def _dict_list(value: Any) -> list[dict]:
    return [item for item in _as_list(value) if isinstance(item, dict)]

def normalize_structured_resume(data: dict[str, Any]) -> dict[str, Any]:
    """
    cleanup function that converts messy LLM JSON  
     """
    data = _as_dict(data)
    contact = _as_dict(data.get("contact"))
    raw_skills = data.get("skills")

    skill_groups = []
    for item in _as_list(raw_skills):
        if isinstance(item, dict):
            items = _clean_list(item.get("items") or item.get("skills"))
            if items:
                skill_groups.append({
                    "category": _text(item.get("category")) or "Skills",
                    "items": items,
                })
        elif _text(item):
            skill_groups.append({"category": "Skills", "items": [_text(item)]})

    legacy_tech = _clean_list(data.get("techSkills"))
    legacy_soft = _clean_list(data.get("softSkills"))
    if not skill_groups and legacy_tech:
        skill_groups.append({"category": "Technical", "items": legacy_tech})
    if legacy_soft:
        skill_groups.append({"category": "Soft Skills", "items": legacy_soft})

    return {
        "name": _text(data.get("name")),
        "contact": {
            "email": _text(contact.get("email")),
            "phone": _text(contact.get("phone")),
            "linkedin": _text(contact.get("linkedin")),
            "github": _text(contact.get("github")),
            "portfolio": _text(contact.get("portfolio")),
        },
        "education": [
            {
                "institution": _text(item.get("institution")),
                "location": _clean_location(
                    _text(item.get("institution")),
                    _text(item.get("location")),
                ),
                "duration": _text(item.get("duration")),
                "degree": " ".join(
                    x for x in [
                        _text(item.get("degree")),
                        _text(item.get("field")),
                    ] if x
                ).strip(),
                "score": _format_score(_text(item.get("score"))),
            }
            for item in _dict_list(data.get("education"))
        ],
        "experience": [
            {
                "title": _text(item.get("title") or item.get("role")),
                "organization": _text(item.get("organization") or item.get("company")),
                "location": _text(item.get("location")),
                "duration": _text(item.get("duration")),
                "certificate": _text(item.get("certificate")),
                "bullets": _clean_list(item.get("bullets") or item.get("description")),
            }
            for item in _dict_list(data.get("experience"))
        ],
        "projects": [
            {
                "name": _text(item.get("name")),
                "github": _text(item.get("github"))
                or (_clean_list(item.get("links"))[0] if _clean_list(item.get("links")) else ""),
                "technologies": _clean_list(item.get("technologies") or item.get("techStack")),
                "bullets": _clean_list(_as_list(item.get("bullets")) + _as_list(item.get("description"))),
            }
            for item in _dict_list(data.get("projects"))
        ],
        "skills": skill_groups,
        "certifications": _clean_list(data.get("certifications")),
        "achievements": _clean_list(data.get("achievements")),
    }

def render_structured_resume(resume: dict[str, Any]) -> str:
    """
     takes structured resume JSON and converts it into one plain text resume string.
    """
    lines: list[str] = []

    name = resume.get("name", "")
    contact = resume.get("contact", {})

    if name:
        lines.append(name)

    contact_parts = [
        contact.get("email", ""),
        contact.get("phone", ""),
        contact.get("linkedin", ""),
        contact.get("github", ""),
        contact.get("portfolio", ""),
    ]
    contact_line = " | ".join([x for x in contact_parts if x])
    if contact_line:
        lines.append(contact_line)

    if resume.get("education"):
        lines.extend(["", "Education"])
        for edu in resume["education"]:
            school = ", ".join(
                x for x in [
                    edu.get("institution", ""),
                    edu.get("location", ""),
                ]
                if x
            )
            if school and edu.get("duration"):
                lines.append(f"{school} | {edu['duration']}")
            elif school:
                lines.append(school)
            elif edu.get("duration"):
                lines.append(edu["duration"])

            if edu.get("degree"):
                lines.append(edu["degree"])
            if edu.get("score"):
                lines.append(edu["score"])

    if resume.get("skills"):
        lines.extend(["", "Technical Skills"])
        for group in resume["skills"]:
            category = group.get("category", "Skills")
            items = ", ".join(group.get("items", []))
            if items:
                lines.append(f"{category}: {items}")

    if resume.get("experience"):
        lines.extend(["", "Experience"])
        for exp in resume["experience"]:
            title = exp.get("title", "")
            if title and exp.get("certificate"):
                title = f"{title} [{exp['certificate']}]"
            if title:
                lines.append(title)
            if exp.get("duration"):
                lines.append(exp["duration"])

            org = ", ".join(
                x for x in [
                    exp.get("organization", ""),
                    exp.get("location", ""),
                ] if x
            )
            if org:
                lines.append(org)

            for bullet in exp.get("bullets", []):
                lines.append(f"- {bullet}")

    if resume.get("projects"):
        lines.extend(["", "Projects"])
        for index, project in enumerate(resume["projects"]):
            if project.get("name"):
                lines.append(project["name"])
            if project.get("github"):
                lines.append(f"GitHub: {project['github']}")
            tech = ", ".join(project.get("technologies", []))
            if tech:
                lines.append(f"Technologies used: {tech}")

            for bullet in project.get("bullets", []):
                lines.append(f"- {bullet}")
            if index < len(resume["projects"]) - 1:
                lines.append("")

    if resume.get("certifications"):
        lines.extend(["", "Certifications"])
        lines.append(", ".join(resume["certifications"]))

    if resume.get("achievements"):
        lines.extend(["", "Achievements"])
        for achievement in resume["achievements"]:
            lines.append(f"- {achievement}")

    return "\n".join(lines).strip()

def write_resume_from_profile(
    candidate_profile: dict,
    ranked_projects: list,
    target_role: str,
    jd_analysis: dict | None = None,
) -> dict[str, Any]:
    """
    Builder writer:
    1. Creates structured resume JSON using the user's schema.
    2. Renders it into resume_text for existing UI/export compatibility.
    """
    structured_resume = build_structured_resume_json(
        candidate_profile=candidate_profile,
        ranked_projects=ranked_projects,
        target_role=target_role,
        jd_analysis=jd_analysis,
    )

    resume_text = render_structured_resume(structured_resume)

    if not resume_text:
        raise ValueError("LLM returned empty structured resume.")

    return {
        "resume_text": resume_text,
        "structured_resume": structured_resume,
    }
