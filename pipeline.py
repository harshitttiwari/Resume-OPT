"""LangGraph orchestration for the Agentic Resume Optimizer."""
from __future__ import annotations
from typing import Any
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from exporter import export_resume
from optimizer_llm import rewrite_resume_with_llm
from matcher import ats_score, gap_report, match_skills, missing_skill_suggestions
from parser import analyze_job_description, load_resume_file, parse_resume, validate_inputs
from validator import extract_metrics, quality_report, remove_added_summary, truth_report
from log import get_logger
log = get_logger(__name__)

# State
class ResumeState(TypedDict):
    resume_file_path: str
    job_description: str
    target_role: str
    export_format: str
    raw_resume: str
    parsed_resume: dict
    jd_analysis: dict
    must_keep_metrics: list
    original_matches: dict
    original_score: float
    final_matches: dict
    ats_score: float
    ats_breakdown: dict
    rewritten: str
    final_resume: str
    truth: dict
    quality: dict
    comparison: dict
    repair_done: bool
    export_status: str
    export_path: str | None

# Nodes
def node_load_validate(state: ResumeState) -> dict:
    log.info("Loading and validating resume...")
    raw = load_resume_file(state["resume_file_path"])
    raw, jd, role, fmt = validate_inputs(
        raw, state["job_description"], state["target_role"], state["export_format"]
    )
    return {
        "raw_resume": raw,
        "job_description": jd,
        "target_role": role,
        "export_format": fmt,
    }

def node_parse_analyze(state: ResumeState) -> dict:
    log.info("Parsing resume and analyzing JD...")
    parsed = parse_resume(state["raw_resume"])
    jd = analyze_job_description(state["job_description"])
    metrics = extract_metrics(state["raw_resume"])
    return {
        "parsed_resume": parsed,
        "jd_analysis": jd,
        "must_keep_metrics": metrics,
    }

def node_match_score(state: ResumeState) -> dict:
    log.info("Matching skills and calculating baseline ATS score...")
    matches = match_skills(state["parsed_resume"], state["jd_analysis"], state["raw_resume"])
    score, _ = ats_score(state["jd_analysis"], matches)
    return {"original_matches": matches, "original_score": score}

def node_rewrite(state: ResumeState) -> dict:
    log.info("Rewriting resume with LLM...")
    payload = {
        "raw_resume_text":  state["raw_resume"],
        "parsed_resume":    state["parsed_resume"],
        "jd_analysis":      state["jd_analysis"],
        "matched_skills":   state["original_matches"]["matched_skills"],
        "missing_skills":   state["original_matches"]["missing_skills"],
        "target_role":      state["target_role"],
        "must_keep_metrics": state["must_keep_metrics"],
    }
    rewritten = rewrite_resume_with_llm(payload)
    final = remove_added_summary(state["raw_resume"], rewritten)
    return {"rewritten": rewritten, "final_resume": final}

def node_validate(state: ResumeState) -> dict:
    log.info("Running truth, metric, and quality checks...")
    final = state["final_resume"]
    jd = state["jd_analysis"]
    matches = match_skills(state["parsed_resume"], jd, final)
    score, breakdown = ats_score(jd, matches)
    truth = truth_report(state["raw_resume"], final)
    quality, comparison = quality_report(state["raw_resume"], final, score, truth, jd)
    return {
        "final_matches": matches,
        "ats_score": score,
        "ats_breakdown": breakdown,
        "truth": truth,
        "quality": quality,
        "comparison": comparison,
    }

def node_repair(state: ResumeState) -> dict:
    log.info("Repair pass triggered - fixing metrics/keywords/hallucinations...")
    comparison = state["comparison"]
    quality = state["quality"]
    original_score = state["original_score"]
    score = state["ats_score"]

    dropped_terms = [
        t for t in comparison.get("original_matched_terms", [])
        if t not in comparison.get("optimized_matched_terms", [])
    ]
    missing_metrics = quality.get("metric_report", {}).get("missing_metrics", [])
    notes = [
        "Restore useful project and experience detail that was compressed.",
        "Keep all facts grounded in the original resume.",
    ]
    if missing_metrics:
        notes.append(f"Re-add these original metrics exactly: {missing_metrics}")
    if dropped_terms:
        notes.append(f"Re-add these supported JD terms if factual: {dropped_terms}")
    if score < original_score:
        notes.append(f"Do not reduce ATS coverage below {original_score:.1f}.")
    feedback = "\n".join(f"- {n}" for n in notes)

    payload = {
        "raw_resume_text":   state["raw_resume"],
        "parsed_resume":     state["parsed_resume"],
        "jd_analysis":       state["jd_analysis"],
        "matched_skills":    state["original_matches"]["matched_skills"],
        "missing_skills":    state["final_matches"]["missing_skills"],
        "target_role":       state["target_role"],
        "must_keep_metrics": state["must_keep_metrics"],
        "current_draft":     state["final_resume"],
        "rewrite_feedback":  feedback,
    }
    rewritten = rewrite_resume_with_llm(payload)
    final = remove_added_summary(state["raw_resume"], rewritten)
    return {"rewritten": rewritten, "final_resume": final, "repair_done": True}

def node_export(state: ResumeState) -> dict:
    log.info("Exporting final resume...")
    quality = state["quality"]
    truth = state["truth"]
    if quality["is_ready_for_export"] and truth["is_truthful"]:
        path = export_resume(state["final_resume"], state["export_format"])
        return {"export_status": "ready", "export_path": path}
    return {"export_status": "draft_needs_review", "export_path": None}

# Conditional routing
def route_after_validate(state: ResumeState) -> str:
    if state.get("repair_done"):
        return "export"   # only one repair pass allowed
    quality = state["quality"]
    truth = state["truth"]
    metrics_lost = bool(quality.get("metric_report", {}).get("missing_metrics"))
    score_regressed = state["ats_score"] < state["original_score"]
    has_false_claims = not truth.get("is_truthful")
    quality_failed = not quality.get("is_ready_for_export")
    if metrics_lost or score_regressed or has_false_claims or quality_failed:
        return "repair"
    return "export"

# Graph assembly
def _build_graph() -> Any:
    graph = StateGraph(ResumeState)

    graph.add_node("load_validate",  node_load_validate)
    graph.add_node("parse_analyze",  node_parse_analyze)
    graph.add_node("match_score",    node_match_score)
    graph.add_node("rewrite",        node_rewrite)
    graph.add_node("validate",       node_validate)
    graph.add_node("repair",         node_repair)
    graph.add_node("export",         node_export)

    graph.set_entry_point("load_validate")
    graph.add_edge("load_validate", "parse_analyze")
    graph.add_edge("parse_analyze", "match_score")
    graph.add_edge("match_score",   "rewrite")
    graph.add_edge("rewrite",       "validate")
    graph.add_conditional_edges("validate", route_after_validate, {
        "repair": "repair",
        "export": "export",
    })
    graph.add_edge("repair",  "validate")
    graph.add_edge("export",  END)

    return graph.compile()

_graph = _build_graph()

# Public entry point
def run_resume_optimizer(
    resume_file_path: str,
    job_description: str,
    target_role: str,
    export_format: str = "docx",
) -> dict[str, Any]:
    initial_state: ResumeState = {
        "resume_file_path": resume_file_path,
        "job_description":  job_description,
        "target_role":      target_role,
        "export_format":    export_format,
        "raw_resume":       "",
        "parsed_resume":    {},
        "jd_analysis":      {},
        "must_keep_metrics": [],
        "original_matches": {},
        "original_score":   0.0,
        "final_matches":    {},
        "ats_score":        0.0,
        "ats_breakdown":    {},
        "rewritten":        "",
        "final_resume":     "",
        "truth":            {},
        "quality":          {},
        "comparison":       {},
        "repair_done":      False,
        "export_status":    "draft_needs_review",
        "export_path":      None,
    }

    final_state = _graph.invoke(initial_state)
    matches = final_state["final_matches"]
    score = final_state["ats_score"]
    quality = final_state["quality"]

    return {
        "raw_resume_text":          final_state["raw_resume"],
        "job_description":          final_state["job_description"],
        "target_role":              final_state["target_role"],
        "parsed_resume":            final_state["parsed_resume"],
        "jd_analysis":              final_state["jd_analysis"],
        "matched_skills":           matches["matched_skills"],
        "missing_skills":           matches["missing_skills"],
        "skill_evidence":           matches["skill_evidence"],
        "ats_score":                score,
        "original_ats_score":       final_state["original_score"],
        "ats_breakdown":            final_state["ats_breakdown"],
        "gap_report":               gap_report(score, matches["matched_skills"], matches["missing_skills"]),
        "missing_skill_suggestions": missing_skill_suggestions(matches["missing_skills"]),
        "rewritten_resume":         final_state["rewritten"],
        "final_resume":             final_state["final_resume"],
        "hallucination_report":     final_state["truth"],
        "quality_report":           quality,
        "ats_comparison":           final_state["comparison"],
        "export_status":            final_state["export_status"],
        "export_path":              final_state["export_path"],
    }