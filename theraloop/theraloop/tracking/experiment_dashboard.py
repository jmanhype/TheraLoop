#!/usr/bin/env python3
"""
MLflow experiment dashboard and visualization server for TheraLoop.
Provides real-time monitoring and analysis of GEPA experiments.
"""

from __future__ import annotations
import mlflow
from mlflow.tracking import MlflowClient
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Optional
import os


class TheraLoopDashboard:
    """Interactive dashboard for TheraLoop MLflow experiments."""
    
    def __init__(self, tracking_uri: str = "http://localhost:5000"):
        """Initialize dashboard with MLflow client."""
        mlflow.set_tracking_uri(tracking_uri)
        self.client = MlflowClient(tracking_uri)
        self.tracking_uri = tracking_uri
    
    def get_experiment_runs(
        self,
        experiment_name: str = "TheraLoop-GEPA",
        max_results: int = 1000
    ) -> pd.DataFrame:
        """Retrieve and format experiment runs."""
        experiment = self.client.get_experiment_by_name(experiment_name)
        if not experiment:
            return pd.DataFrame()
        
        runs = self.client.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=["start_time DESC"],
            max_results=max_results
        )
        
        # Convert to DataFrame
        data = []
        for run in runs:
            row = {
                "run_id": run.info.run_id,
                "run_name": run.info.run_name,
                "status": run.info.status,
                "start_time": datetime.fromtimestamp(run.info.start_time / 1000),
                "end_time": datetime.fromtimestamp(run.info.end_time / 1000) if run.info.end_time else None,
                "duration_s": (run.info.end_time - run.info.start_time) / 1000 if run.info.end_time else None
            }
            
            # Add params
            for key, value in run.data.params.items():
                row[f"params.{key}"] = value
            
            # Add metrics
            for key, value in run.data.metrics.items():
                row[f"metrics.{key}"] = value
            
            # Add tags
            for key, value in run.data.tags.items():
                row[f"tags.{key}"] = value
            
            data.append(row)
        
        return pd.DataFrame(data)
    
    def render_dashboard(self):
        """Render Streamlit dashboard."""
        st.set_page_config(
            page_title="TheraLoop MLflow Dashboard",
            page_icon="🧬",
            layout="wide"
        )
        
        st.title("🧬 TheraLoop GEPA Evolution Dashboard")
        st.markdown(f"Connected to: `{self.tracking_uri}`")
        
        # Sidebar controls
        with st.sidebar:
            st.header("Configuration")
            
            # Experiment selection
            experiments = self.client.search_experiments()
            exp_names = [exp.name for exp in experiments]
            selected_exp = st.selectbox(
                "Select Experiment",
                exp_names,
                index=exp_names.index("TheraLoop-GEPA") if "TheraLoop-GEPA" in exp_names else 0
            )
            
            # Time range filter
            time_range = st.selectbox(
                "Time Range",
                ["Last Hour", "Last 24 Hours", "Last Week", "All Time"],
                index=1
            )
            
            # Refresh button
            if st.button("🔄 Refresh Data"):
                st.rerun()
        
        # Get runs data
        runs_df = self.get_experiment_runs(selected_exp)
        
        if runs_df.empty:
            st.warning("No runs found for selected experiment")
            return
        
        # Apply time filter
        now = datetime.now()
        if time_range == "Last Hour":
            runs_df = runs_df[runs_df["start_time"] > now - timedelta(hours=1)]
        elif time_range == "Last 24 Hours":
            runs_df = runs_df[runs_df["start_time"] > now - timedelta(days=1)]
        elif time_range == "Last Week":
            runs_df = runs_df[runs_df["start_time"] > now - timedelta(weeks=1)]
        
        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Runs", len(runs_df))
        with col2:
            if "metrics.max_score" in runs_df.columns:
                st.metric("Best Score", f"{runs_df['metrics.max_score'].max():.4f}")
        with col3:
            if "params.generation" in runs_df.columns:
                st.metric("Max Generation", int(runs_df["params.generation"].max()))
        with col4:
            if "metrics.convergence_rate" in runs_df.columns:
                st.metric("Avg Convergence", f"{runs_df['metrics.convergence_rate'].mean():.3f}")
        
        # Main visualizations
        st.header("📊 Evolution Analysis")
        
        # Score evolution plot
        if "params.generation" in runs_df.columns and "metrics.avg_score" in runs_df.columns:
            fig_evolution = go.Figure()
            
            # Sort by generation for proper line plot
            plot_df = runs_df.sort_values("params.generation")
            
            fig_evolution.add_trace(go.Scatter(
                x=plot_df["params.generation"],
                y=plot_df["metrics.avg_score"],
                mode="lines+markers",
                name="Average Score",
                line=dict(color="blue", width=2)
            ))
            
            if "metrics.max_score" in plot_df.columns:
                fig_evolution.add_trace(go.Scatter(
                    x=plot_df["params.generation"],
                    y=plot_df["metrics.max_score"],
                    mode="lines+markers",
                    name="Max Score",
                    line=dict(color="green", width=2)
                ))
            
            if "metrics.min_score" in plot_df.columns:
                fig_evolution.add_trace(go.Scatter(
                    x=plot_df["params.generation"],
                    y=plot_df["metrics.min_score"],
                    mode="lines+markers",
                    name="Min Score",
                    line=dict(color="red", width=1, dash="dash")
                ))
            
            fig_evolution.update_layout(
                title="Score Evolution Across Generations",
                xaxis_title="Generation",
                yaxis_title="Score",
                hovermode="x unified",
                height=400
            )
            
            st.plotly_chart(fig_evolution, use_container_width=True)
        
        # Pareto front analysis
        col1, col2 = st.columns(2)
        
        with col1:
            if "params.pareto_size" in runs_df.columns:
                fig_pareto = px.bar(
                    runs_df.sort_values("params.generation"),
                    x="params.generation",
                    y="params.pareto_size",
                    title="Pareto Front Size by Generation",
                    labels={"params.pareto_size": "Pareto Size"},
                    color="params.pareto_size",
                    color_continuous_scale="Viridis"
                )
                st.plotly_chart(fig_pareto, use_container_width=True)
        
        with col2:
            if "params.pool_size" in runs_df.columns:
                fig_pool = px.scatter(
                    runs_df,
                    x="params.pool_size",
                    y="metrics.avg_score" if "metrics.avg_score" in runs_df.columns else "params.generation",
                    size="params.pareto_size" if "params.pareto_size" in runs_df.columns else None,
                    color="params.generation" if "params.generation" in runs_df.columns else None,
                    title="Pool Size vs Performance",
                    labels={"metrics.avg_score": "Average Score"},
                    hover_data=["run_name"]
                )
                st.plotly_chart(fig_pool, use_container_width=True)
        
        # Convergence analysis
        st.header("🎯 Convergence Metrics")
        
        if "metrics.surprise_delta" in runs_df.columns:
            col1, col2 = st.columns(2)
            
            with col1:
                fig_surprise = px.line(
                    runs_df.sort_values("params.generation"),
                    x="params.generation",
                    y="metrics.surprise_delta",
                    title="Surprise Delta Evolution",
                    markers=True
                )
                fig_surprise.add_hline(
                    y=runs_df["metrics.surprise_delta"].mean(),
                    line_dash="dash",
                    annotation_text="Mean"
                )
                st.plotly_chart(fig_surprise, use_container_width=True)
            
            with col2:
                # Score variance over time
                if "metrics.max_score" in runs_df.columns and "metrics.min_score" in runs_df.columns:
                    runs_df["score_variance"] = runs_df["metrics.max_score"] - runs_df["metrics.min_score"]
                    fig_variance = px.area(
                        runs_df.sort_values("params.generation"),
                        x="params.generation",
                        y="score_variance",
                        title="Score Variance (Diversity)",
                        labels={"score_variance": "Max - Min Score"}
                    )
                    st.plotly_chart(fig_variance, use_container_width=True)
        
        # Run details table
        st.header("📋 Run Details")
        
        # Filter columns for display
        display_cols = ["run_name", "status", "start_time"]
        metric_cols = [col for col in runs_df.columns if col.startswith("metrics.")]
        param_cols = [col for col in runs_df.columns if col.startswith("params.")]
        
        display_df = runs_df[display_cols + metric_cols[:5] + param_cols[:5]].head(20)
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Artifact viewer
        st.header("🗂️ Artifacts")
        
        selected_run = st.selectbox(
            "Select Run to View Artifacts",
            runs_df["run_name"].tolist() if "run_name" in runs_df.columns else []
        )
        
        if selected_run:
            run_data = runs_df[runs_df["run_name"] == selected_run].iloc[0]
            run_id = run_data["run_id"]
            
            artifacts = self.client.list_artifacts(run_id)
            if artifacts:
                st.write(f"Artifacts for run: {selected_run}")
                for artifact in artifacts:
                    st.write(f"- {artifact.path} ({artifact.file_size} bytes)")
            else:
                st.info("No artifacts found for this run")
        
        # Export functionality
        st.header("💾 Export Data")
        
        col1, col2 = st.columns(2)
        with col1:
            csv = runs_df.to_csv(index=False)
            st.download_button(
                label="Download Runs as CSV",
                data=csv,
                file_name=f"theraloop_runs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        with col2:
            if st.button("Generate HTML Report"):
                self._generate_html_report(runs_df)
                st.success("HTML report generated!")
    
    def _generate_html_report(self, runs_df: pd.DataFrame):
        """Generate static HTML report with embedded visualizations."""
        from theraloop.tracking.mlflow_artifacts import TheraLoopMLflowTracker
        
        tracker = TheraLoopMLflowTracker(self.tracking_uri)
        
        # Generate interactive dashboard
        dashboard_path = tracker.create_interactive_dashboard(
            runs_df,
            output_path="theraloop_dashboard.html"
        )
        
        st.markdown(f"Report saved to: `{dashboard_path}`")
        
        # Provide download link
        with open(dashboard_path, "rb") as f:
            st.download_button(
                label="Download HTML Dashboard",
                data=f.read(),
                file_name="theraloop_dashboard.html",
                mime="text/html"
            )


def main():
    """Run the dashboard application."""
    dashboard = TheraLoopDashboard(
        tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    )
    dashboard.render_dashboard()


if __name__ == "__main__":
    # Run with: streamlit run experiment_dashboard.py
    main()