"""Streamlit UI for the Agentic Resume Optimizer."""

from __future__ import annotations

import os
import tempfile

import streamlit as st

from pipeline import run_resume_optimizer

st.set_page_config(
    page_title="Agentic Resume Optimizer",
    page_icon=":page_facing_up:",
    layout="wide",
)

MIME_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "txt": "text/plain",
}


def show_list(title: str, items: list[str], empty: str = "None.") -> None:
    st.subheader(title)
    if items:
        for item in items:
            st.write(f"- {item}")
    else:
        st.info(empty)


def render_results(result: dict, export_format: str) -> None:
    status = result.get("export_status", "draft_needs_review")
    if status == "ready":
        st.success("Resume passed all safety checks and is ready to export.")
    else:
        st.warning("Draft only - truth, quality, or metric checks need review before use.")

    comparison = result.get("ats_comparison", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final ATS Score", f"{result.get('ats_score', 0):.1f}/100")
    c2.metric("Original ATS Score", f"{result.get('original_ats_score', 0):.1f}/100")
    c3.metric("Keyword Improvement", f"{comparison.get('improvement', 0):+.1f}")
    c4.metric("Matched Skills", len(result.get("matched_skills", [])))

    tab_resume, tab_skills, tab_ats, tab_validation, tab_evidence = st.tabs(
        ["Resume", "Skills", "ATS", "Validation", "Skill Evidence"]
    )

    with tab_resume:
        st.text_area("Optimized Resume", result.get("final_resume", ""), height=520)

    with tab_skills:
        col1, col2 = st.columns(2)
        with col1:
            show_list("Matched Skills", result.get("matched_skills", []))
        with col2:
            show_list("Missing Skills", result.get("missing_skills", []))
        show_list("Suggestions", result.get("missing_skill_suggestions", []))

    with tab_ats:
        st.subheader("ATS Breakdown")
        st.json(result.get("ats_breakdown", {}))
        st.subheader("Gap Report")
        st.json(result.get("gap_report", {}))
        st.subheader("Before / After Keyword Coverage")
        st.json(comparison)
        with st.expander("Extracted JD Terms"):
            st.json(result.get("jd_analysis", {}))

    with tab_validation:
        quality = result.get("quality_report", {})
        truth = result.get("hallucination_report", {})
        metric = quality.get("metric_report", {})

        st.subheader("Quality Review")
        if quality.get("is_ready_for_export"):
            st.success("Quality checks passed.")
        else:
            st.warning("Quality checks found issues.")
        for issue in quality.get("issues", []):
            st.error(issue)
        for warning in quality.get("warnings", []):
            st.warning(warning)
        for suggestion in quality.get("suggestions", []):
            st.info(suggestion)

        st.subheader("Truth Check")
        if truth.get("is_truthful"):
            st.success("No unsupported claims detected.")
        else:
            st.warning("Potential unsupported claims detected.")
        st.json(truth)

        st.subheader("Metric Preservation")
        st.metric("Preservation Score", f"{metric.get('preservation_score', 0):.0%}")
        st.json(metric)

    with tab_evidence:
        evidence = result.get("skill_evidence", {})
        if not evidence:
            st.info("No skill evidence available.")
        else:
            for skill, items in evidence.items():
                with st.expander(skill):
                    for item in items:
                        st.write(f"- {item.get('text', '')} ({item.get('score', 0):.2f})")

    export_path = result.get("export_path")
    if export_path and os.path.exists(export_path):
        with open(export_path, "rb") as fh:
            st.download_button(
                label=f"Download {export_format.upper()}",
                data=fh.read(),
                file_name=os.path.basename(export_path),
                mime=MIME_TYPES.get(export_format, "application/octet-stream"),
                use_container_width=True,
            )


# Main layout

st.title("Agentic Resume Tools")
mode = st.radio("Select Mode", ["Optimize Existing Resume", "Build Resume from GitHub"], horizontal=True)

if mode == "Build Resume from GitHub":
    import builder_app
    builder_app.render()
    st.caption("ATS tailoring with hallucination and metric safety checks.")
    st.stop()

uploaded_resume = st.file_uploader("Upload Resume (PDF, DOCX, or TXT)", type=["pdf", "docx", "txt"])
job_description = st.text_area("Paste Job Description", height=220)

col_role, col_fmt = st.columns([3, 1])
with col_role:
    target_role = st.text_input("Target Role", placeholder="e.g. Data Analyst, Marketing Manager")
with col_fmt:
    export_format = st.selectbox("Export Format", ["docx", "pdf", "txt"])

if st.button("Optimize Resume", type="primary", use_container_width=True):
    if uploaded_resume is None:
        st.error("Please upload a resume.")
        st.stop()
    if not job_description.strip():
        st.error("Please paste the job description.")
        st.stop()
    if not target_role.strip():
        st.error("Please enter the target role.")
        st.stop()

    suffix = os.path.splitext(uploaded_resume.name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_resume.read())
    tmp.close()

    try:
        with st.spinner("Optimizing resume - this takes about 20-30 seconds..."):
            result = run_resume_optimizer(
                resume_file_path=tmp.name,
                job_description=job_description,
                target_role=target_role,
                export_format=export_format,
            )
        st.session_state["result"] = result
        st.session_state["export_format"] = export_format
    except Exception as exc:
        st.error(f"Optimization failed: {exc}")
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass

if st.session_state.get("result"):
    render_results(
        st.session_state["result"],
        st.session_state.get("export_format", "docx"),
    )
