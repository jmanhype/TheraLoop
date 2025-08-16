#!/usr/bin/env python3
"""
MLflow artifact management and dashboard generation for TheraLoop.
Based on official MLflow documentation patterns.
"""

from __future__ import annotations
import mlflow
import mlflow.sklearn
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import json
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.offline as pyo


class TheraLoopMLflowTracker:
    """MLflow tracking and artifact management for TheraLoop experiments."""
    
    def __init__(
        self,
        tracking_uri: str = "http://localhost:5000",
        experiment_name: str = "TheraLoop-GEPA",
        artifact_location: Optional[str] = None
    ):
        """Initialize MLflow tracking with TheraLoop configuration."""
        mlflow.set_tracking_uri(tracking_uri)
        
        # Create experiment with optional remote artifact store
        if artifact_location:
            self.experiment_id = mlflow.create_experiment(
                experiment_name,
                artifact_location=artifact_location,
                tags={
                    "team": "theraloop",
                    "framework": "dspy-gepa",
                    "version": "0.1.0"
                }
            )
        else:
            mlflow.set_experiment(experiment_name)
            self.experiment = mlflow.get_experiment_by_name(experiment_name)
            self.experiment_id = self.experiment.experiment_id if self.experiment else None
    
    def log_gepa_generation(
        self,
        generation: int,
        pool: List[Dict],
        pareto_front: List[Dict],
        metrics: Dict[str, float]
    ) -> str:
        """Log a GEPA generation as an MLflow run with artifacts."""
        with mlflow.start_run(run_name=f"gepa_gen_{generation}") as run:
            # Log parameters
            mlflow.log_params({
                "generation": generation,
                "pool_size": len(pool),
                "pareto_size": len(pareto_front),
                "scorer_type": metrics.get("scorer", "logprob_hybrid")
            })
            
            # Log metrics
            mlflow.log_metrics({
                "avg_score": np.mean([p["score"] for p in pool if p["score"]]),
                "max_score": max([p["score"] for p in pool if p["score"]], default=0),
                "min_score": min([p["score"] for p in pool if p["score"]], default=0),
                "pareto_avg": np.mean([p["score"] for p in pareto_front if p["score"]]),
                **metrics
            })
            
            # Generate and log visualizations
            artifacts_dir = "mlflow_artifacts"
            os.makedirs(artifacts_dir, exist_ok=True)
            
            # Create Pareto front visualization
            pareto_plot_path = self._create_pareto_visualization(
                generation, pool, pareto_front, artifacts_dir
            )
            mlflow.log_artifact(pareto_plot_path)
            
            # Create score distribution plot
            dist_plot_path = self._create_score_distribution(
                pool, artifacts_dir
            )
            mlflow.log_artifact(dist_plot_path)
            
            # Create surprise delta heatmap
            if "surprise_deltas" in metrics:
                heatmap_path = self._create_surprise_heatmap(
                    metrics["surprise_deltas"], artifacts_dir
                )
                mlflow.log_artifact(heatmap_path)
            
            # Log pool as JSON artifact
            pool_path = os.path.join(artifacts_dir, f"pool_gen_{generation}.json")
            with open(pool_path, "w") as f:
                json.dump(pool, f, indent=2)
            mlflow.log_artifact(pool_path)
            
            # Clean up local artifacts
            for file in os.listdir(artifacts_dir):
                os.remove(os.path.join(artifacts_dir, file))
            os.rmdir(artifacts_dir)
            
            return run.info.run_id
    
    def _create_pareto_visualization(
        self,
        generation: int,
        pool: List[Dict],
        pareto_front: List[Dict],
        artifacts_dir: str
    ) -> str:
        """Create Pareto front visualization."""
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))
        
        # Extract scores
        all_scores = [p["score"] for p in pool if p["score"]]
        pareto_scores = [p["score"] for p in pareto_front if p["score"]]
        
        # Plot 1: Score evolution
        axes[0].scatter(range(len(all_scores)), all_scores, alpha=0.5, label="Pool")
        axes[0].scatter(
            [i for i, p in enumerate(pool) if p in pareto_front],
            pareto_scores,
            color="red",
            s=100,
            label="Pareto Front",
            zorder=5
        )
        axes[0].set_title(f"Generation {generation}: Score Distribution")
        axes[0].set_xlabel("Candidate Index")
        axes[0].set_ylabel("Score")
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # Plot 2: Score histogram
        axes[1].hist(all_scores, bins=20, alpha=0.7, label="All Candidates")
        axes[1].hist(pareto_scores, bins=10, alpha=0.7, color="red", label="Pareto Front")
        axes[1].set_title("Score Distribution")
        axes[1].set_xlabel("Score")
        axes[1].set_ylabel("Count")
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        path = os.path.join(artifacts_dir, f"pareto_gen_{generation}.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        return path
    
    def _create_score_distribution(
        self,
        pool: List[Dict],
        artifacts_dir: str
    ) -> str:
        """Create score distribution analysis."""
        scores = [p["score"] for p in pool if p["score"]]
        
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # Box plot
        axes[0, 0].boxplot(scores)
        axes[0, 0].set_title("Score Distribution (Box Plot)")
        axes[0, 0].set_ylabel("Score")
        
        # Violin plot
        axes[0, 1].violinplot(scores)
        axes[0, 1].set_title("Score Distribution (Violin)")
        axes[0, 1].set_ylabel("Score")
        
        # CDF
        sorted_scores = np.sort(scores)
        cdf = np.arange(1, len(sorted_scores) + 1) / len(sorted_scores)
        axes[1, 0].plot(sorted_scores, cdf)
        axes[1, 0].set_title("Cumulative Distribution")
        axes[1, 0].set_xlabel("Score")
        axes[1, 0].set_ylabel("CDF")
        axes[1, 0].grid(True, alpha=0.3)
        
        # QQ plot
        from scipy import stats
        stats.probplot(scores, dist="norm", plot=axes[1, 1])
        axes[1, 1].set_title("Q-Q Plot")
        
        plt.tight_layout()
        path = os.path.join(artifacts_dir, "score_distribution.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        return path
    
    def _create_surprise_heatmap(
        self,
        surprise_deltas: List[float],
        artifacts_dir: str
    ) -> str:
        """Create surprise delta heatmap."""
        # Reshape for heatmap (assuming square-ish layout)
        n = len(surprise_deltas)
        grid_size = int(np.ceil(np.sqrt(n)))
        padded = surprise_deltas + [0] * (grid_size**2 - n)
        grid = np.array(padded).reshape(grid_size, grid_size)
        
        plt.figure(figsize=(10, 8))
        sns.heatmap(
            grid,
            annot=False,
            cmap="coolwarm",
            center=0,
            cbar_kws={"label": "Surprise Delta"}
        )
        plt.title("Logprob Surprise Delta Heatmap")
        plt.xlabel("Candidate Column")
        plt.ylabel("Candidate Row")
        
        path = os.path.join(artifacts_dir, "surprise_heatmap.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        return path
    
    def create_interactive_dashboard(
        self,
        experiment_runs: pd.DataFrame,
        output_path: str = "dashboard.html"
    ) -> str:
        """Create interactive Plotly dashboard for experiment analysis."""
        fig = make_subplots(
            rows=3,
            cols=2,
            subplot_titles=(
                "Score Evolution Across Generations",
                "Pareto Front Size Progression",
                "Score Distribution by Generation",
                "Convergence Analysis",
                "Pool Diversity Metrics",
                "Best Score Trajectory"
            ),
            specs=[
                [{"secondary_y": False}, {"secondary_y": False}],
                [{"secondary_y": False}, {"secondary_y": False}],
                [{"secondary_y": False}, {"secondary_y": False}]
            ]
        )
        
        # Score evolution
        fig.add_trace(
            go.Scatter(
                x=experiment_runs["params.generation"],
                y=experiment_runs["metrics.avg_score"],
                mode="lines+markers",
                name="Avg Score",
                line=dict(color="blue")
            ),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=experiment_runs["params.generation"],
                y=experiment_runs["metrics.max_score"],
                mode="lines+markers",
                name="Max Score",
                line=dict(color="green")
            ),
            row=1, col=1
        )
        
        # Pareto front size
        fig.add_trace(
            go.Bar(
                x=experiment_runs["params.generation"],
                y=experiment_runs["params.pareto_size"],
                name="Pareto Size",
                marker_color="purple"
            ),
            row=1, col=2
        )
        
        # Score distribution boxplot
        for gen in experiment_runs["params.generation"].unique():
            gen_data = experiment_runs[experiment_runs["params.generation"] == gen]
            fig.add_trace(
                go.Box(
                    y=[gen_data["metrics.min_score"].values[0],
                       gen_data["metrics.avg_score"].values[0],
                       gen_data["metrics.max_score"].values[0]],
                    name=f"Gen {gen}",
                    boxmean=True
                ),
                row=2, col=1
            )
        
        # Convergence rate
        score_diffs = experiment_runs["metrics.max_score"].diff()
        fig.add_trace(
            go.Scatter(
                x=experiment_runs["params.generation"],
                y=score_diffs,
                mode="lines+markers",
                name="Score Delta",
                line=dict(color="orange")
            ),
            row=2, col=2
        )
        
        # Pool diversity (score variance)
        score_variance = experiment_runs.apply(
            lambda r: (r["metrics.max_score"] - r["metrics.min_score"]), axis=1
        )
        fig.add_trace(
            go.Scatter(
                x=experiment_runs["params.generation"],
                y=score_variance,
                mode="lines+markers",
                name="Score Range",
                fill="tozeroy",
                line=dict(color="red")
            ),
            row=3, col=1
        )
        
        # Best score trajectory with trend
        fig.add_trace(
            go.Scatter(
                x=experiment_runs["params.generation"],
                y=experiment_runs["metrics.max_score"].cummax(),
                mode="lines+markers",
                name="Best Score",
                line=dict(color="darkgreen", width=3)
            ),
            row=3, col=2
        )
        
        # Update layout
        fig.update_layout(
            title_text="TheraLoop GEPA Evolution Dashboard",
            showlegend=True,
            height=1200,
            hovermode="x unified"
        )
        
        # Update axes
        fig.update_xaxes(title_text="Generation", row=3, col=1)
        fig.update_xaxes(title_text="Generation", row=3, col=2)
        fig.update_yaxes(title_text="Score", row=1, col=1)
        fig.update_yaxes(title_text="Count", row=1, col=2)
        
        # Save interactive dashboard
        pyo.plot(fig, filename=output_path, auto_open=False)
        return output_path
    
    def log_calibration_metrics(
        self,
        roc_data: Dict[str, Any],
        threshold: float,
        precision: float,
        recall: float
    ):
        """Log router calibration metrics and ROC curve."""
        with mlflow.start_run(run_name="router_calibration"):
            mlflow.log_params({
                "calibration_type": "roc_based",
                "threshold": threshold,
                "target_precision": 0.85
            })
            
            mlflow.log_metrics({
                "precision": precision,
                "recall": recall,
                "f1_score": 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0,
                "auc": roc_data.get("auc", 0)
            })
            
            # Create ROC curve
            if "fpr" in roc_data and "tpr" in roc_data:
                fig, ax = plt.subplots(figsize=(8, 8))
                ax.plot(roc_data["fpr"], roc_data["tpr"], label=f"ROC (AUC={roc_data['auc']:.3f})")
                ax.plot([0, 1], [0, 1], "k--", label="Random")
                ax.axvline(x=threshold, color="r", linestyle=":", label=f"Threshold={threshold:.3f}")
                ax.set_xlabel("False Positive Rate")
                ax.set_ylabel("True Positive Rate")
                ax.set_title("Router Calibration ROC Curve")
                ax.legend()
                ax.grid(True, alpha=0.3)
                
                mlflow.log_figure(fig, "roc_curve.png")
                plt.close()
    
    def track_hierarchical_runs(
        self,
        parent_name: str = "theraloop_sweep",
        configurations: List[Dict[str, Any]] = None
    ):
        """Track hierarchical runs for hyperparameter sweeps."""
        with mlflow.start_run(run_name=parent_name) as parent_run:
            mlflow.log_param("search_strategy", "pareto_optimization")
            
            best_score = 0
            best_config = {}
            
            for config in configurations or []:
                with mlflow.start_run(
                    nested=True,
                    run_name=f"config_{config.get('id', 'unknown')}"
                ) as child_run:
                    mlflow.log_params(config)
                    
                    # Simulate evaluation
                    score = config.get("score", np.random.random())
                    mlflow.log_metric("eval_score", score)
                    
                    if score > best_score:
                        best_score = score
                        best_config = config
            
            # Log best to parent
            mlflow.log_params({f"best_{k}": v for k, v in best_config.items()})
            mlflow.log_metric("best_score", best_score)
            
            return parent_run.info.run_id


def setup_mlflow_integration():
    """Setup complete MLflow integration for TheraLoop."""
    tracker = TheraLoopMLflowTracker(
        tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        experiment_name="TheraLoop-Production",
        artifact_location=os.getenv("MLFLOW_ARTIFACT_LOCATION")  # Optional S3/Azure
    )
    
    # Enable autologging for supported frameworks
    mlflow.autolog()
    
    return tracker


if __name__ == "__main__":
    # Example usage
    tracker = setup_mlflow_integration()
    
    # Simulate GEPA generation logging
    mock_pool = [
        {"prompt": f"prompt_{i}", "score": np.random.random()}
        for i in range(10)
    ]
    mock_pareto = mock_pool[:3]
    
    run_id = tracker.log_gepa_generation(
        generation=1,
        pool=mock_pool,
        pareto_front=mock_pareto,
        metrics={
            "surprise_delta": 0.15,
            "convergence_rate": 0.8
        }
    )
    
    print(f"Logged generation to run: {run_id}")