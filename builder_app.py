"""Streamlit UI for Agentic Resume Builder."""
from __future__ import annotations
import os
import tempfile #import tempfile
import uuid #avoid filename conflicts when many users upload or export resumes
import streamlit as st
from builder_pipeline import BuilderState, run_builder_after_answers, run_builder_until_questions
from github_tools import extract_github_username
from log import get_logger

log = get_logger(__name__)

def show_event_trace(state: dict) -> None:
    st.subheader("Event Trace")
    events = state.get("event_trace", [])
    if not events:
        st.info("No events yet.")
        return

    for entry in events:
        step = entry.get("step", "unknown_step")
        status = entry.get("status", "success")
        details = entry.get("details", {})

        with st.expander(f"{step} - {status}"):
            st.write("Step:", step)
            st.write("Status:", status)
            if details:
                st.json(details)
            else:
                st.caption("No extra details.")

def render():
    st.title("Agentic Resume Builder")
    st.caption("Build an ATS-friendly resume from your GitHub profile, LinkedIn URL, and a few questions.")

    # Inputs
    with st.form("builder_inputs"):
        github_url   = st.text_input("GitHub URL *", placeholder="https://github.com/yourusername")
        linkedin_url = st.text_input("LinkedIn URL (optional)", placeholder="https://linkedin.com/in/yourprofile")
        linkedin_zip = st.file_uploader(
            "LinkedIn data export ZIP (optional)",
            type=["zip"],
            help="Download from LinkedIn -> Settings & Privacy -> Data Privacy -> Get a copy of your data",)
        portfolio_url = st.text_input("Portfolio URL (optional)")
        target_role = st.text_input("Target Role *", placeholder="GenAI Engineer Intern / Software Developer")

        builder_export_format = st.selectbox(
            "Export Format",
            ["md", "docx", "txt"],
            help="Markdown is simplest for review. DOCX is best for final resume download.")

        old_resume = st.file_uploader("Upload old resume (optional)", type=["pdf", "docx", "txt"])
        submitted = st.form_submit_button("Start Building", type="primary", use_container_width=True)

    linkedin_data = {}
    if linkedin_zip:
        from github_tools import parse_linkedin_zip
        linkedin_data = parse_linkedin_zip(linkedin_zip.read())
        log.info(f"LinkedIn ZIP parsed: {list(linkedin_data.keys())}")

    if submitted:
        if not github_url.strip() or not target_role.strip():
            st.error("GitHub URL and Target Role are required.")
            st.stop()

        normalized_github = github_url.strip()
        normalized_linkedin = linkedin_url.strip()

        # Common input mistake: URLs entered in opposite fields.
        if "linkedin.com" in normalized_github.lower() and "github.com" in normalized_linkedin.lower():
            normalized_github, normalized_linkedin = normalized_linkedin, normalized_github
            st.info("GitHub and LinkedIn URLs looked swapped, so they were corrected automatically.")

        try:
            extract_github_username(normalized_github)
        except ValueError as exc:
            st.error(f"Invalid GitHub URL: {exc}")
            st.stop()

        session_id = str(uuid.uuid4())[:8]
        old_resume_path = None

        if old_resume:
            suffix = os.path.splitext(old_resume.name)[1]
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(old_resume.read())
            tmp.close()
            old_resume_path = tmp.name

        initial: BuilderState = {
            "github_url":     normalized_github,
            "linkedin_url":   normalized_linkedin,
            "portfolio_url":  portfolio_url.strip(),
            "target_role":    target_role.strip(),
            "old_resume_path": old_resume_path,
            "export_format": builder_export_format,
            "source_status": {},
            "github_profile": {},
            "github_repos":   [],
            "repo_analysis":  [],
            "old_resume_text": "",
            "missing_questions": [],
            "user_answers":   {},
            "candidate_profile": {},
            "ranked_projects": [],
            "resume_draft":   "",
            "validation_report": {},
            "human_feedback": "",
            "final_resume":   "",
            "structured_resume": {},
            "event_trace":    [],
            "export_path":    None,
            "session_id":     session_id,
            "linkedin_data": linkedin_data,
        }
        log.info("Starting GitHub fetch and repo analysis...")

        try:
            with st.spinner("Fetching GitHub data and analyzing projects..."):
                state = run_builder_until_questions(initial)

            st.session_state["builder_state"] = state
            st.session_state["phase"] = "questions"
            st.rerun()

        except Exception as exc:
            st.error(str(exc))
            st.stop()

    # Phase: Answer missing questions
    if st.session_state.get("phase") == "questions":
        state = st.session_state["builder_state"]
        questions = state.get("missing_questions", [])

        st.subheader("A few questions to complete your profile")
        answers = {}
        with st.form("missing_answers"):
            for i, q in enumerate(questions):
                answers[f"q{i}"] = st.text_input(q, key=f"ans_{i}")
            proceed = st.form_submit_button("Build Resume", type="primary", use_container_width=True)

        if proceed:
            user_answers = {questions[i]: answers[f"q{i}"] for i in range(len(questions))}
            state["user_answers"] = user_answers

            log.info("Building candidate profile and writing resume...")

            try:
                with st.spinner("Building your resume..."):
                    state = run_builder_after_answers(state)

                st.session_state["builder_state"] = state
                st.session_state["phase"] = "review"
                st.rerun()

            except Exception as exc:
                st.error(f"Resume building failed: {exc}")
                st.stop()

    # Phase: Human review
    if st.session_state.get("phase") == "review":
        state = st.session_state["builder_state"]

        st.subheader("Review Your Resume Draft")
        draft = state.get("resume_draft", "")
        report = state.get("validation_report", {})

        col1, col2 = st.columns([2, 1])
        with col1:
            edited = st.text_area("Edit if needed", draft, height=600)
        with col2:
            st.subheader("Claim Validation")
            if report.get("unsafe_claims"):
                for c in report["unsafe_claims"]:
                    st.error(c)
            if report.get("needs_confirmation"):
                for c in report["needs_confirmation"]:
                    st.warning(c)
            if report.get("safe_claims"):
                st.success(f"{len(report['safe_claims'])} claims fully verified.")

            show_event_trace(state)

        if st.button("Export Resume", type="primary", use_container_width=True):
            log.info("Exporting final resume...")
            state["human_feedback"] = edited
            try:
                from builder_pipeline import node_export
                updates = node_export(state)
                state = {**state, **updates}
                st.session_state["builder_state"] = state
                st.session_state["phase"] = "done"
                st.rerun()
            except Exception as exc:
                st.error(f"Export failed: {exc}")
                st.stop()

    # Phase: Done

    if st.session_state.get("phase") == "done":
        state = st.session_state["builder_state"]
        st.success("Resume built and exported successfully.")
        export_path = state.get("export_path")
        if export_path and os.path.exists(export_path):
            with open(export_path, "rb") as f:
                export_format = state.get("export_format", "md")
                mime_map = {
                            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            "md": "text/markdown",
                            "txt": "text/plain",}

                st.download_button(
                            f"Download Resume ({export_format.upper()})",
                            f.read(),
                            file_name=f"built_resume.{export_format}",
                            mime=mime_map.get(export_format, "application/octet-stream"),
                            use_container_width=True,)
