"""Deterministic skill matching and ATS scoring."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

SEMANTIC_ALIASES = {
    "version control":    ["git", "github", "gitlab", "bitbucket"],
    "cloud platforms":    ["aws", "azure", "gcp", "google cloud", "heroku", "vertex ai"],
    "containerization":   ["docker", "kubernetes", "podman"],
    "ci/cd":              ["github actions", "jenkins", "gitlab ci", "circleci"],
    "databases":          ["postgresql", "mysql", "mongodb", "sqlite", "redis"],
    "vector databases":   ["chromadb", "pinecone", "faiss", "weaviate", "qdrant"],
    "data visualization": ["tableau", "power bi", "matplotlib", "plotly"],
    "agile":              ["scrum", "jira", "kanban", "sprint"],
}

# Text normalisation

def normalize(text: str) -> str:
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9+#./% -]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def stem(word: str) -> str:
    word = word.lower().strip()
    if len(word) <= 3 or re.search(r"[0-9+#]", word):
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("ation") and len(word) > 7:
        return word[:-5]
    if word.endswith("ing") and len(word) > 5:
        word = word[:-3]
    elif word.endswith("ed") and len(word) > 4:
        word = word[:-2]
    elif word.endswith("ment") and len(word) > 6:
        word = word[:-4]
    elif word.endswith("es") and word[:-2].endswith(("s", "x", "z", "ch", "sh")):
        word = word[:-2]
    elif word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    return word


def token_stems(text: str) -> set[str]:
    """Generic word stems handling punctuation, plurals, and suffix variation."""
    words = re.findall(r"[a-z0-9+#]+", normalize(text).replace("/", " ").replace("-", " "))
    stems = set()
    for word in words:
        stems.add(stem(word))
        if word.endswith("ed") and len(word) > 4:
            stems.add(word[:-1])   # walked -> walke (helps fuzzy overlap)
    return stems


def acronym(term: str) -> str:
    letters = [w[0] for w in re.findall(r"[A-Za-z]+", term) if w]
    return "".join(letters).lower() if len(letters) > 1 else ""


# Variant generation

def variants(term: str) -> list[str]:
    """Generic text variants: casing, punctuation, slash splits, plurals, acronyms."""
    raw = str(term or "").strip()
    base = normalize(raw)
    out = [raw, base]

    no_parens = re.sub(r"\([^)]*\)", " ", raw)
    out.append(no_parens)
    out += re.findall(r"\(([^)]*)\)", raw)

    for chunk in re.split(r"[/,&]| or | and ", raw, flags=re.IGNORECASE):
        if chunk.strip():
            out.append(chunk.strip())

    out += [raw.replace("-", " "), raw.replace("_", " ")]

    words = normalize(raw).split()
    if len(words) > 1:
        out.append(" ".join(words))
        short = acronym(raw)
        if short:
            out.append(short)
    elif words:
        word = words[0]
        out.append(word[:-1] if word.endswith("s") and len(word) > 3 else f"{word}s")

    seen, clean = set(), []
    for item in out:
        key = normalize(item)
        if key and key not in seen:
            seen.add(key)
            clean.append(item)
    return clean


# Acronym matching

def acronym_phrase_match(text: str, term: str) -> bool:
    """Match an acronym in text to its spelled-out phrase."""
    target = re.sub(r"[^a-z0-9]", "", normalize(term))
    if target.endswith("s") and len(target) > 3 and str(term or "")[-1:].islower():
        target = target[:-1]
    if not (3 <= len(target) <= 6) or " " in normalize(term):
        return False
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]*", text)
    for i in range(len(words) - len(target) + 1):
        phrase = words[i: i + len(target)]
        if not any(w[:1].isupper() for w in phrase):
            continue
        if "".join(w[0].lower() for w in phrase) == target:
            return True
    return False


def embedded_acronym_match(text: str, term: str) -> bool:
    """Match acronym sequences inside camelCase/PascalCase tokens (e.g. FastAPI)."""
    target = re.sub(r"s$", "", re.sub(r"[^a-z0-9]", "", normalize(term)))
    if not (3 <= len(target) <= 6):
        return False
    if not any(c.isupper() for c in str(term or "")):
        return False
    for token in re.findall(r"[A-Za-z0-9+#.]+", text):
        if target in token.lower() and any(c.isupper() for c in token[1:]):
            return True
    return False


# Core matching

def contains_term(text: str, term: str) -> bool:
    haystack = normalize(text)
    if not normalize(term):
        return False
    for item in variants(term):
        item_norm = normalize(item)
        pattern = r"(?<![a-z0-9])" + re.escape(item_norm) + r"(?![a-z0-9])"
        if item_norm and re.search(pattern, haystack):
            return True
    if len(token_stems(term)) > 1 and token_stems(term).issubset(token_stems(text)):
        return True
    if acronym_phrase_match(text, term):
        return True
    if embedded_acronym_match(text, term):
        return True
    return False


def similarity(term: str, unit: str) -> float:
    if contains_term(unit, term):
        return 1.0
    term_tokens: set[str] = set()
    for item in variants(term):
        term_tokens |= token_stems(item)
    unit_tokens = token_stems(unit)
    if not term_tokens or len(term_tokens) == 1:
        return 0.0
    overlap = len(term_tokens & unit_tokens) / len(term_tokens)
    fuzzy = SequenceMatcher(None, normalize(term), normalize(unit)).ratio()
    return round(max(overlap, fuzzy if fuzzy >= 0.82 else 0), 3)



def evidence_units(parsed: dict[str, Any], raw_text: str) -> list[str]:
    """Collect all searchable text units from structured parse and raw resume."""
    units: list[str] = []
    units += parsed.get("skills", [])
    units += parsed.get("certifications", [])
    for p in parsed.get("projects", []):
        units += [p.get("title", ""), p.get("description", ""), p.get("impact", "")]
        units += p.get("tech_stack", [])
    for job in parsed.get("experience", []):
        units += [job.get("company", ""), job.get("role", ""), job.get("duration", "")]
        units += job.get("bullet_points", [])
    for school in parsed.get("education", []):
        units += [school.get("degree", ""), school.get("institution", ""), school.get("year", "")]
    units += [line.strip() for line in raw_text.splitlines() if len(line.strip()) > 6]

    seen, out = set(), []
    for unit in units:
        clean = re.sub(r"\s+", " ", str(unit or "")).strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            out.append(clean)
    return out


def terms_from_jd(jd: dict[str, Any], include_keywords: bool = False) -> list[str]:
    keys = ["required_skills", "preferred_skills", "tools"]
    if include_keywords:
        keys.append("keywords")
    seen, terms = set(), []
    for key in keys:
        for term in jd.get(key, []) or []:
            clean = str(term).strip()
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                terms.append(clean)
    return terms


# Scoring

def _alias_match(skill: str, units: list[str]) -> bool:
    aliases = SEMANTIC_ALIASES.get(skill.lower())
    if not aliases:
        return False
    text = " ".join(units).lower()
    return any(alias in text for alias in aliases)


def match_skills(parsed: dict[str, Any], jd: dict[str, Any], raw_text: str) -> dict[str, Any]:
    units = evidence_units(parsed, raw_text)
    matched, missing, evidence = [], [], {}

    for skill in terms_from_jd(jd, include_keywords=True):
        scored = sorted(
            [{"text": unit, "score": similarity(skill, unit)} for unit in units],
            key=lambda item: item["score"],
            reverse=True,
        )[:3]
        n_tokens = len(token_stems(skill))
        # Single-token: require exact match; 2-token: 0.80; 3+: 0.75
        threshold = 1.0 if n_tokens == 1 else (0.80 if n_tokens == 2 else 0.75)
        if (scored and scored[0]["score"] >= threshold) or _alias_match(skill, units):
            matched.append(skill)
            evidence[skill] = scored
        else:
            missing.append(skill)

    return {"matched_skills": matched, "missing_skills": missing, "skill_evidence": evidence}


def ats_score(jd: dict[str, Any], matches: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    all_skills = terms_from_jd(jd, include_keywords=True)
    required = {normalize(x) for x in jd.get("required_skills", [])}
    matched = {normalize(x) for x in matches.get("matched_skills", [])}
    total = max(len(all_skills), 1)
    required_total = max(len(required), 1)

    coverage = len(matched) / total
    required_coverage = len(required & matched) / required_total
    scores = [items[0]["score"] for items in matches.get("skill_evidence", {}).values() if items]
    evidence_quality = sum(scores) / len(scores) if scores else 0
    missing_required = len(required - matched)
    penalty = min(missing_required * 2.0, 10.0)
    score = max(0.0, min(100.0, coverage * 50 + required_coverage * 35 + evidence_quality * 15 - penalty))

    return round(score, 2), {
        "skill_coverage_score": round(coverage * 50, 2),
        "required_score":       round(required_coverage * 35, 2),
        "evidence_score":       round(evidence_quality * 15, 2),
        "missing_penalty":      penalty,
        "matched_count":        len(matched),
        "missing_count":        len(matches.get("missing_skills", [])),
        "total_jd_skills":      len(all_skills),
    }


def gap_report(score: float, matched: list[str], missing: list[str]) -> dict[str, Any]:
    if score >= 85:
        level, rec = "Strong match", "Only minor wording improvements are needed."
    elif score >= 70:
        level, rec = "Good match", "Improve keyword placement and evidence clarity."
    elif score >= 55:
        level, rec = "Moderate match", "Relevant experience exists but alignment can improve."
    else:
        level, rec = "Weak match", "Apply only if the missing skills are not core requirements."
    total = len(matched) + len(missing)
    return {
        "ats_score":             score,
        "match_ratio":           round(len(matched) / total, 2) if total else 0,
        "match_level":           level,
        "matched_skills_count":  len(matched),
        "missing_skills_count":  len(missing),
        "missing_skills":        missing,
        "recommendation":        rec,
    }


def missing_skill_suggestions(missing: list[str]) -> list[str]:
    # Capped at 8 for UI readability; full list is available in gap_report
    return [
        f"If true, add evidence showing {skill}; otherwise leave it out."
        for skill in missing[:8]
    ]
