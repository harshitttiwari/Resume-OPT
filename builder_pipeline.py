"""Two-phase pipeline for building a resume from GitHub evidence."""

from __future__ import annotations

import json
import time
from pathlib import Path

from typing_extensions import TypedDict

from exporter import export_resume
from github_tools import (
    fetch_github_profile,
    fetch_github_repos,
    fetch_readme,
)
from llm import (
    analyze_repo_with_llm,
    build_candidate_profile,
    generate_missing_questions,
    validate_resume_claims,
    write_resume_from_profile,
)
from log import get_logger
from parser import load_resume_file

log = get_logger(__name__)
PERSIST_DIR = Path("sessions")


# State

class BuilderState(TypedDict):
    github_url: str
    linkedin_url: str
    portfolio_url: str
    target_role: str
    old_resume_path: str | None
    export_format: str
    source_status: dict
    github_profile: dict
    github_repos: list
    repo_analysis: list
    old_resume_text: str
    missing_questions: list
    user_answers: dict
    candidate_profile: dict
    ranked_projects: list
    resume_draft: str
    validation_report: dict
    human_feedback: str
    final_resume: str
    structured_resume: dict
    event_trace: list
    export_path: str | None
    session_id: str
    linkedin_data: dict

# Persistence

def _save_session(state: BuilderState) -> None:
    sid = state.get("session_id", "default")
    PERSIST_DIR.mkdir(exist_ok=True)
    path = PERSIST_DIR / f"{sid}.json"
    serializable = {k: v for k, v in state.items() if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
    path.write_text(json.dumps(serializable, indent=2))


def add_event(state: BuilderState, step: str, status: str = "success", details: dict = None) -> list:
    return state.get("event_trace", []) + [{
        "step": step,
        "status": status,
        "details": details or {}
    }]


# Nodes

def node_source_checker(state: BuilderState) -> dict:
    log.info("Checking available sources...")

    status = {
        "github": bool(state.get("github_url")),
        "linkedin": bool(state.get("linkedin_url")),
        "linkedin_export": bool(state.get("linkedin_data")),
        "portfolio": bool(state.get("portfolio_url")),
        "old_resume": bool(state.get("old_resume_path")),
    }

    trace = add_event(
        state,
        "source_check",
        "success",
        status
    )

    return {
        "source_status": status,
        "event_trace": trace,
    }


def node_github_fetch(state: BuilderState) -> dict:
    log.info("Fetching GitHub profile and repos...")

    url = state.get("github_url", "")

    try:
        profile = fetch_github_profile(url)
        repos = fetch_github_repos(url)

        trace = add_event(
            state,
            "github_fetch",
            "success",
            {"repos_found": len(repos)}
        )

        updates = {
            "github_profile": profile,
            "github_repos": repos,
            "event_trace": trace,
        }

        _save_session({**state, **updates})
        return updates

    except Exception as exc:
        error_message = str(exc)

        trace = add_event(
            state,
            "github_fetch",
            "failed",
            {"error": error_message}
        )

        updates = {
            "github_profile": {},
            "github_repos": [],
            "event_trace": trace,
        }

        _save_session({**state, **updates})
        raise ValueError(f"GitHub fetch failed. Please check the GitHub URL. Details: {error_message}") from exc


def node_readme_analyzer(state: BuilderState) -> dict:
    log.info("Analyzing repos and README files...")

    repos = state.get("github_repos", [])
    target_role = state.get("target_role", "")
    analysis = []
    failed_repos = []

    for repo in repos[:8]:
        repo_name = repo.get("name", "")

        try:
            readme = fetch_readme(state["github_url"], repo_name)
            result = analyze_repo_with_llm(repo, readme, target_role)

            result["repo_url"] = repo.get("url", "")
            result["repo_name"] = repo_name
            result["readme_available"] = bool(readme.strip())

            analysis.append(result)

        except Exception as exc:
            log.info(f"Repo analysis failed for {repo_name}: {exc}")

            failed_repos.append({
                "repo_name": repo_name,
                "error": str(exc),
            })

            # Fallback analysis so the repo is not completely lost
            analysis.append({
                "project_name": repo_name,
                "repo_url": repo.get("url", ""),
                "repo_name": repo_name,
                "problem": repo.get("description", ""),
                "tech_stack": [repo.get("language", "")] if repo.get("language") else [],
                "features": [],
                "evidence": [
                    repo.get("description", "")
                ] if repo.get("description") else [],
                "resume_strength": 1,
                "recommended_for_roles": [],
                
                "readme_available": False,
            })

        time.sleep(0.5)

    trace = add_event(
        state,
        "readme_analysis",
        "success",
        {
            "repos_analyzed": len(analysis),
            "failed_repos": len(failed_repos),
        }
    )

    _save_session({**state, "repo_analysis": analysis, "event_trace": trace})

    return {
        "repo_analysis": analysis,
        "event_trace": trace,
    }



def node_linkedin_safe(state: BuilderState) -> dict:
    log.info("Storing LinkedIn URL safely (no scraping)...")
    url = state.get("linkedin_url", "")
    trace = add_event(state, "linkedin_safe", "success", {"provided": bool(url)})
    return {"event_trace": trace}


def node_resume_parser(state: BuilderState) -> dict:
    path = state.get("old_resume_path")
    if not path:
        return {"old_resume_text": ""}
    log.info("Parsing uploaded old resume...")
    try:
        text = load_resume_file(path)
    except Exception as e:
        log.info(f"Resume parse failed: {e}")
        text = ""
    trace = add_event(state, "resume_parse", "success", {"chars_parsed": len(text)})
    return {"old_resume_text": text, "event_trace": trace}


def node_missing_questions(state: BuilderState) -> dict:
    log.info("Generating missing information questions...")

    partial_profile = {
        "target_role": state.get("target_role", ""),
        "github_profile": {
            "name": state.get("github_profile", {}).get("name", ""),
            "bio": state.get("github_profile", {}).get("bio", ""),
            "location": state.get("github_profile", {}).get("location", ""),
            "public_repos": state.get("github_profile", {}).get("public_repos", 0),
        },
        "top_repo_analysis": state.get("repo_analysis", [])[:5],
        "linkedin_url_provided": bool(state.get("linkedin_url")),
        "linkedin_export_available": bool(state.get("linkedin_data")),
        "linkedin_data_keys": list(state.get("linkedin_data", {}).keys()),
        "has_old_resume": bool(state.get("old_resume_text")),
        "old_resume_preview": state.get("old_resume_text", "")[:1500],
    }

    result = generate_missing_questions(
        partial_profile,
        state.get("target_role", ""),
    )

    questions = result.get("questions", [])

    trace = add_event(
        state,
        "question_generation",
        "success",
        {"questions_count": len(questions)}
    )

    return {
        "missing_questions": questions,
        "event_trace": trace,
    }


def node_candidate_profile_builder(state: BuilderState) -> dict:
    log.info("Building unified candidate profile...")

    merged_answers = {
        **state.get("user_answers", {}),
        "linkedin_url": state.get("linkedin_url", ""),
        "portfolio_url": state.get("portfolio_url", ""),
        "linkedin_data": state.get("linkedin_data", {}),
    }

    profile = build_candidate_profile(
        github_profile=state["github_profile"],
        repo_analysis=state["repo_analysis"],
        old_resume=state.get("old_resume_text", ""),
        user_answers=merged_answers,
        target_role=state["target_role"],
    )

    if state.get("linkedin_url"):
        profile["linkedin_url"] = state["linkedin_url"]
    if state.get("portfolio_url"):
        profile["portfolio_url"] = state["portfolio_url"]
    if state.get("github_url") and not profile.get("github_url"):
        profile["github_url"] = state["github_url"]

    trace = add_event(
        state,
        "profile_build",
        "success",
        {
            "projects": len(profile.get("projects", [])),
            "skills": len(profile.get("skills", [])),
        },
    )

    _save_session({**state, "candidate_profile": profile, "event_trace": trace})
    return {
        "candidate_profile": profile,
        "event_trace": trace,
    }


def node_project_ranker(state: BuilderState) -> dict:
    log.info("Ranking projects by relevance to target role...")

    target_role = state.get("target_role", "").lower()
    repo_analysis = state.get("repo_analysis", [])

    def project_score(project: dict) -> float:
        base_score = float(project.get("resume_strength", 0) or 0)

        recommended_roles = " ".join(project.get("recommended_for_roles", [])).lower()
        tech_stack = " ".join(project.get("tech_stack", [])).lower()
        project_name = str(project.get("project_name", "") or project.get("repo_name", "")).lower()
        repo_name = str(project.get("repo_name", "")).lower()
        problem = str(project.get("problem", "")).lower()
        evidence = project.get("evidence", []) or []
        features = project.get("features", []) or []

        searchable_text = " ".join([
            recommended_roles,
            tech_stack,
            project_name,
            repo_name,
            problem,
            " ".join(map(str, features)),
            " ".join(map(str, evidence)),
        ])

        role_bonus = 2.0 if target_role and target_role in searchable_text else 0.0
        evidence_bonus = min(len(evidence), 4) * 0.25
        feature_bonus = min(len(features), 4) * 0.20
        readme_bonus = 0.5 if project.get("readme_available") else 0.0

        penalty = 0.0

        # Penalize weak/generic repository names.
        # This prevents repos like "Resume", "test", or "demo" from ranking above real projects.
        weak_names = {
            "resume",
            "test",
            "demo",
            "practice",
            "portfolio",
            "frontend",
            "backend",
            "website",
            "my-website",
            "personal-website",
        }

        if project_name.strip() in weak_names or repo_name.strip() in weak_names:
            penalty += 3.0

        # Penalize repos with almost no useful project evidence.
        if not project.get("problem") and not features and not evidence:
            penalty += 2.0

        return base_score + role_bonus + evidence_bonus + feature_bonus + readme_bonus - penalty

    ranked = sorted(
        repo_analysis,
        key=project_score,
        reverse=True,
    )[:4]

    trace = add_event(
        state,
        "project_ranking",
        "success",
        {"selected_projects": [p.get("project_name", "") for p in ranked]}
    )

    return {
        "ranked_projects": ranked,
        "event_trace": trace,
    }


def node_resume_writer(state: BuilderState) -> dict:
    log.info("Writing resume from candidate profile...")
    result = write_resume_from_profile(
        candidate_profile=state["candidate_profile"],
        ranked_projects=state["ranked_projects"],
        target_role=state["target_role"],
    )
    draft = result.get("resume_text", "")
    structured = result.get("structured_resume", {})
    trace = add_event(
        state,
        "resume_write",
        "success",
        {
            "draft_chars": len(draft),
            "projects": len(structured.get("projects", [])) if isinstance(structured, dict) else 0,
        },
    )
    updates = {
        "resume_draft": draft,
        "structured_resume": structured,
        "event_trace": trace,
    }
    _save_session({**state, **updates})
    return updates


def node_claim_validator(state: BuilderState) -> dict:
    log.info("Validating resume claims against evidence...")

    report = validate_resume_claims(
        resume_text=state["resume_draft"],
        candidate_profile=state["candidate_profile"],
        repo_analysis=state.get("ranked_projects") or state["repo_analysis"],
        old_resume_text=state.get("old_resume_text", ""),
        user_answers=state.get("user_answers", {}),
    )

    trace = add_event(
        state,
        "claim_validation",
        "success",
        {
            "safe": len(report.get('safe_claims', [])),
            "needs_confirmation": len(report.get('needs_confirmation', [])),
            "unsafe": len(report.get('unsafe_claims', []))
        }
    )

    return {
        "validation_report": report,
        "event_trace": trace,
    }


def node_export(state: BuilderState) -> dict:
    log.info("Exporting final resume...")

    resume = state.get("human_feedback") or state.get("resume_draft", "")
    export_format = state.get("export_format", "md")

    path = export_resume(resume, export_format)

    trace = add_event(state, "export", "success", {"format": export_format})

    _save_session({
        **state,
        "final_resume": resume,
        "export_path": path,
        "event_trace": trace,
    })

    return {
        "final_resume": resume,
        "export_path": path,
        "event_trace": trace,
    }



# Graph

def run_builder_until_questions(initial_state: BuilderState) -> BuilderState:
    """
    Run the builder workflow until missing questions are generated.
    Streamlit will pause here so the user can answer questions.
    """
    state = initial_state

    for fn in [
        node_source_checker,
        node_github_fetch,
        node_readme_analyzer,
        node_linkedin_safe,
        node_resume_parser,
        node_missing_questions,
    ]:
        updates = fn(state)
        state = {**state, **updates}

    _save_session(state)
    return state


def run_builder_after_answers(state: BuilderState) -> BuilderState:
    """
    Continue the builder workflow after the user answers clarification questions.
    """
    for fn in [
        node_candidate_profile_builder,
        node_project_ranker,
        node_resume_writer,
        node_claim_validator,
    ]:
        updates = fn(state)
        state = {**state, **updates}

    _save_session(state)
    return state

