"""Truth, metric, quality, and export-safety checks."""
from __future__ import annotations
import re
from typing import Any
from optimizer_llm import truth_check_with_llm
from matcher import contains_term, terms_from_jd

# Metric extraction
METRIC_PATTERNS = [
    r"\b(?:CGPA|GPA)[:\s]*\d(?:\.\d+)?(?:/\d(?:\.\d+)?)?\b",
    r"\b\d{1,3}(?:\.\d+)?\s*%\+?",           # percentages (covers Grade/Score/Marks too)
    r"\b\d{1,6}\+\b",                          # counts like "500+ users"
    r"\b\d+[-\s]?tokens?\b",
    r"\bsub[-\s]?\d+\s*ms\b",
    r"\b\d+(?:\.\d+)?\s*(?:ms|sec|seconds|milliseconds)\b",
    r"\b\d+\s*(?:years?|yrs|months?|weeks?|days?)\b",
    r"\b\d{4}(?:[-/]\d{2,4})?\b",             # dates and year ranges
]

WEAK_PHRASES = [
    "responsible for", "worked on", "helped with",
    "assisted with", "involved in", "participated in",
]

def _compact(text: str) -> str:
    """Normalise a metric string to a comparison key."""
    text = str(text or "").lower().replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9%+./]", "", text)   # strip colons, spaces, dashes for stable keying

def extract_metrics(text: str) -> list[str]:
    """Extract numeric metrics from resume text using regex patterns."""
    found, seen = [], set()
    for pattern in METRIC_PATTERNS:
        for match in re.findall(pattern, text or "", flags=re.IGNORECASE):
            metric = re.sub(r"\s+", " ", str(match)).strip()
            key = _compact(metric)
            if metric and key not in seen:
                seen.add(key)
                found.append(metric)
    return found

def metric_report(original: str, rewritten: str) -> dict[str, Any]:
    """rack whether numeric metrics from the original resume are preserved"""
    original_metrics = extract_metrics(original)
    rewritten_keys = {_compact(x) for x in extract_metrics(rewritten)}
    preserved, missing = [], []
    for metric in original_metrics:
        (preserved if _compact(metric) in rewritten_keys else missing).append(metric)
    score = len(preserved) / len(original_metrics) if original_metrics else 1.0
    return {
        "original_metrics":   original_metrics,
        "preserved_metrics":  preserved,
        "missing_metrics":    missing,
        "preservation_score": round(score, 3),
        "is_metric_safe":     score >= 0.8,
    }

# Keyword comparison
def keyword_comparison(original: str, final: str, jd: dict[str, Any]) -> dict[str, Any]:
    """Compare how well the original and optimized resume match JD"""
    terms = terms_from_jd(jd, include_keywords=True)
    original_hits = [t for t in terms if contains_term(original, t)]
    final_hits = [t for t in terms if contains_term(final, t)]
    total = max(len(terms), 1)
    original_score = round(len(original_hits) / total * 100, 2)
    final_score = round(len(final_hits) / total * 100, 2)
    return {
        "original_ats_score":    original_score,
        "optimized_ats_score":   final_score,
        "improvement":           round(final_score - original_score, 2),
        "original_matched_terms":  original_hits,
        "optimized_matched_terms": final_hits,
        "still_missing_terms":   [t for t in terms if t not in final_hits],
    }

# Summary removal
def _original_has_summary(text: str) -> bool:
    """Check if the original resume already contains a summary section"""
    return bool(re.search(
        r"(?im)^\s*(summary|profile|objective|professional summary)\s*$",
        text or "",
    ))

def remove_added_summary(original: str, rewritten: str) -> str:
    """Strip LLM-added career summary sections that were not in the original."""
    if _original_has_summary(original):
        return rewritten
    lines = rewritten.splitlines()
    headings = {"summary", "profile", "objective", "professional summary"}
    all_headings = headings | {
        "skills", "technical skills", "projects",
        "experience", "education", "certifications",
    }
    start = next(
        (i for i, line in enumerate(lines) if line.strip().lower().strip("*:") in headings),
        None,
    )
    if start is None:
        return rewritten
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].strip().lower().strip("*:") in all_headings:
            end = i
            break
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines[:start] + lines[end:])).strip()

# Truth checking
def _remove_truth_false_positives(report: dict[str, Any], original: str) -> dict[str, Any]:
    """
    Filter LLM truth-check issues where all quoted terms are present in the original.
    """
    issues = []
    original_compact = _compact(original)
    for issue in report.get("issues", []):
        quoted = [a or b for a, b in re.findall(r'"([^"]+)"|\'([^\']+)\'', str(issue))]
        if quoted and all(_compact(t) in original_compact for t in quoted):
            continue
        issues.append(str(issue))
    return {"is_truthful": not issues, "issues": issues}

def truth_report(original: str, rewritten: str) -> dict[str, Any]:
    return _remove_truth_false_positives(truth_check_with_llm(original, rewritten), original)

# Quality gate
def quality_report(
    original: str,
    final: str,
    ats: float,
    truth: dict[str, Any],
    jd: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    issues: list[str] = []
    warnings: list[str] = []
    suggestions: list[str] = []

    if len(final.strip()) < 500:
        issues.append("Resume output is too short.")
        suggestions.append("Add more verified projects, skills, or achievements.")

    if not truth.get("is_truthful"):
        issues.append("Potential hallucination detected.")
        suggestions.append("Remove unsupported claims before exporting.")

    for phrase in WEAK_PHRASES:
        if phrase in final.lower():
            warnings.append(f"Weak phrase found: '{phrase}'")

    if ats < 70:
        warnings.append(f"ATS score is below recommended level ({ats}/100).")

    metrics = metric_report(original, final)
    if metrics["missing_metrics"]:
        issues.append(
            "Important metrics missing after rewrite: "
            + ", ".join(metrics["missing_metrics"])
        )
        suggestions.append("Preserve key numeric achievements exactly.")

    if not issues:
        suggestions.append("Resume passed all safety checks and is ready for export.")

    comparison = keyword_comparison(original, final, jd)

    return {
        "issues":             issues,
        "warnings":           warnings,
        "suggestions":        suggestions,
        "is_ready_for_export": not issues,
        "metric_report":      metrics,
    }, comparison
