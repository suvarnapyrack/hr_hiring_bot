"""
analytics.py — Analytics Dashboard for HR Hiring Bot
Renders plotly charts inside Streamlit for score distributions,
accept/reject ratios, resumes-over-time, skills frequency, and source breakdown.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy.orm import Session
from app.crud import (
    get_score_distribution,
    get_accept_reject_counts,
    get_resumes_over_time,
    get_skills_frequency,
    get_source_distribution,
)
from app.models import Candidate, Resume


def show_analytics_page(db: Session):
    """Main function — render the full Analytics Dashboard."""

    st.markdown("## 📊 Analytics Dashboard")
    st.markdown("Visual insights on all candidates processed through the pipeline.")
    st.markdown("---")

    # ── Top-level summary metrics ─────────────────────────────────────────────
    total_candidates = db.query(Candidate).count()
    total_resumes = db.query(Resume).count()
    ar_counts = get_accept_reject_counts(db)
    accepted = ar_counts.get("Accepted", 0)
    rejected = ar_counts.get("Rejected", 0)
    accept_rate = round((accepted / total_resumes * 100), 1) if total_resumes > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 Total Candidates", total_candidates)
    c2.metric("📄 Total Resumes", total_resumes)
    c3.metric("✅ Accepted", accepted)
    c4.metric("📈 Accept Rate", f"{accept_rate}%")

    st.markdown("<br>", unsafe_allow_html=True)

    if total_resumes == 0:
        st.info("💡 No data yet. Process some resumes first to see analytics.")
        return

    # ── Row 1: Score Distribution + Accept/Reject Pie ────────────────────────
    row1_col1, row1_col2 = st.columns([3, 2])

    with row1_col1:
        score_data = get_score_distribution(db)
        if score_data:
            df_scores = pd.DataFrame(score_data)
            fig_hist = px.histogram(
                df_scores, x="score", nbins=20,
                title="📊 Score Distribution",
                labels={"score": "Final Score", "count": "Candidates"},
                color_discrete_sequence=["#667eea"],
                template="plotly_white"
            )
            fig_hist.update_layout(
                title_font_size=16,
                showlegend=False,
                height=350,
                bargap=0.1
            )
            fig_hist.add_vline(x=6.5, line_dash="dash", line_color="#ef4444",
                               annotation_text="Threshold (6.5)", annotation_position="top right")
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("No score data available.")

    with row1_col2:
        if accepted + rejected > 0:
            fig_pie = go.Figure(data=[go.Pie(
                labels=["✅ Accepted", "❌ Rejected"],
                values=[accepted, rejected],
                hole=0.45,
                marker_colors=["#10b981", "#ef4444"]
            )])
            fig_pie.update_layout(
                title="🎯 Accept vs Reject",
                title_font_size=16,
                height=350,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2)
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)

    # ── Row 2: Resumes Over Time + Source Breakdown ───────────────────────────
    row2_col1, row2_col2 = st.columns([3, 2])

    with row2_col1:
        time_data = get_resumes_over_time(db)
        if time_data and len(time_data) > 1:
            df_time = pd.DataFrame(time_data)
            df_time["date"] = pd.to_datetime(df_time["date"])
            fig_time = px.line(
                df_time, x="date", y="count",
                title="📅 Resumes Processed Over Time",
                labels={"date": "Date", "count": "Resumes"},
                markers=True,
                color_discrete_sequence=["#764ba2"],
                template="plotly_white"
            )
            fig_time.update_layout(height=320, title_font_size=16)
            fig_time.update_traces(line_width=2.5, marker_size=7)
            st.plotly_chart(fig_time, use_container_width=True)
        else:
            st.info("📅 Need multiple days of data for time chart.")

    with row2_col2:
        source_data = get_source_distribution(db)
        if source_data:
            df_source = pd.DataFrame(source_data)
            fig_source = px.pie(
                df_source, names="source", values="count",
                title="📥 Resume Sources",
                color_discrete_sequence=px.colors.qualitative.Set2,
                template="plotly_white"
            )
            fig_source.update_layout(height=320, title_font_size=16)
            st.plotly_chart(fig_source, use_container_width=True)

    # ── Row 3: Top Skills Bar Chart ────────────────────────────────────────────
    st.markdown("---")
    skills_data = get_skills_frequency(db, top_n=15)
    if skills_data:
        df_skills = pd.DataFrame(skills_data)
        fig_skills = px.bar(
            df_skills, x="count", y="skill",
            orientation="h",
            title="🔧 Top Skills Across All Candidates",
            labels={"count": "Frequency", "skill": "Skill"},
            color="count",
            color_continuous_scale=["#e0e7ff", "#667eea", "#4338ca"],
            template="plotly_white"
        )
        fig_skills.update_layout(
            height=450, title_font_size=16,
            yaxis=dict(categoryorder="total ascending"),
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_skills, use_container_width=True)
    else:
        st.info("No skills data available yet.")
