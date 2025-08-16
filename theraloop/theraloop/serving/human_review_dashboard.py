#!/usr/bin/env python3
"""
Human-in-the-Loop Review Dashboard
=================================
Web-based dashboard for human reviewers to validate DSPy predictions,
especially for edge cases and ensemble disagreements.

Features:
- Queue of cases requiring human review
- Side-by-side model predictions
- Clinical assessment interface
- Feedback collection for continuous learning
- Performance analytics

Author: TheraLoop Team
"""

import streamlit as st
import pandas as pd
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import plotly.express as px
import plotly.graph_objects as go

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ReviewCase:
    """Case requiring human review"""
    case_id: str
    user_message: str
    conversation_context: List[Dict[str, str]]
    timestamp: datetime
    
    # Model predictions
    primary_prediction: Dict[str, Any]
    validator_prediction: Dict[str, Any]
    intent_prediction: Dict[str, Any]
    ensemble_prediction: Dict[str, Any]
    
    # Review status
    review_status: str  # pending, in_review, completed
    reviewer_id: Optional[str] = None
    human_classification: Optional[str] = None
    human_confidence: Optional[float] = None
    clinical_notes: Optional[str] = None
    review_timestamp: Optional[datetime] = None
    
    # Flags
    model_disagreement: bool = False
    low_confidence: bool = False
    safety_critical: bool = False


class ReviewDashboard:
    """Human review dashboard for DSPy predictions"""
    
    def __init__(self, db_path: str = None):
        import os
        self.db_path = db_path or os.getenv("THERALOOP_DB_PATH", "theraloop.db")
        self.init_database()
    
    def init_database(self):
        """Initialize review database tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create review cases table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_cases (
                    case_id TEXT PRIMARY KEY,
                    user_message TEXT NOT NULL,
                    conversation_context TEXT,
                    timestamp TEXT NOT NULL,
                    
                    primary_prediction TEXT,
                    validator_prediction TEXT,
                    intent_prediction TEXT,
                    ensemble_prediction TEXT,
                    
                    review_status TEXT DEFAULT 'pending',
                    reviewer_id TEXT,
                    human_classification TEXT,
                    human_confidence REAL,
                    clinical_notes TEXT,
                    review_timestamp TEXT,
                    
                    model_disagreement BOOLEAN DEFAULT FALSE,
                    low_confidence BOOLEAN DEFAULT FALSE,
                    safety_critical BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Create reviewer feedback table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reviewer_feedback (
                    feedback_id TEXT PRIMARY KEY,
                    case_id TEXT,
                    reviewer_id TEXT,
                    model_name TEXT,
                    feedback_type TEXT,
                    feedback_text TEXT,
                    improvement_suggestion TEXT,
                    timestamp TEXT,
                    FOREIGN KEY (case_id) REFERENCES review_cases (case_id)
                )
            """)
            
            conn.commit()
            conn.close()
            logger.info("Review dashboard database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize review database: {e}")
    
    def add_review_case(self, case: ReviewCase):
        """Add a case to the review queue"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO review_cases VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                case.case_id,
                case.user_message,
                json.dumps(case.conversation_context),
                case.timestamp.isoformat(),
                json.dumps(case.primary_prediction),
                json.dumps(case.validator_prediction),
                json.dumps(case.intent_prediction),
                json.dumps(case.ensemble_prediction),
                case.review_status,
                case.reviewer_id,
                case.human_classification,
                case.human_confidence,
                case.clinical_notes,
                case.review_timestamp.isoformat() if case.review_timestamp else None,
                case.model_disagreement,
                case.low_confidence,
                case.safety_critical
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Added review case: {case.case_id}")
            
        except Exception as e:
            logger.error(f"Failed to add review case: {e}")
    
    def get_pending_cases(self) -> List[ReviewCase]:
        """Get all pending review cases"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM review_cases 
                WHERE review_status = 'pending' 
                ORDER BY timestamp DESC
            """)
            
            cases = []
            for row in cursor.fetchall():
                case = ReviewCase(
                    case_id=row[0],
                    user_message=row[1],
                    conversation_context=json.loads(row[2]) if row[2] else [],
                    timestamp=datetime.fromisoformat(row[3]),
                    primary_prediction=json.loads(row[4]) if row[4] else {},
                    validator_prediction=json.loads(row[5]) if row[5] else {},
                    intent_prediction=json.loads(row[6]) if row[6] else {},
                    ensemble_prediction=json.loads(row[7]) if row[7] else {},
                    review_status=row[8],
                    reviewer_id=row[9],
                    human_classification=row[10],
                    human_confidence=row[11],
                    clinical_notes=row[12],
                    review_timestamp=datetime.fromisoformat(row[13]) if row[13] else None,
                    model_disagreement=bool(row[14]),
                    low_confidence=bool(row[15]),
                    safety_critical=bool(row[16])
                )
                cases.append(case)
            
            conn.close()
            return cases
            
        except Exception as e:
            logger.error(f"Failed to get pending cases: {e}")
            return []
    
    def submit_review(self, case_id: str, reviewer_id: str, 
                     human_classification: str, human_confidence: float,
                     clinical_notes: str):
        """Submit human review for a case"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE review_cases SET
                    review_status = 'completed',
                    reviewer_id = ?,
                    human_classification = ?,
                    human_confidence = ?,
                    clinical_notes = ?,
                    review_timestamp = ?
                WHERE case_id = ?
            """, (
                reviewer_id,
                human_classification,
                human_confidence,
                clinical_notes,
                datetime.now().isoformat(),
                case_id
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Submitted review for case: {case_id}")
            
        except Exception as e:
            logger.error(f"Failed to submit review: {e}")
    
    def get_review_analytics(self) -> Dict[str, Any]:
        """Get analytics on review performance"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Total cases
            total_cases = pd.read_sql_query(
                "SELECT COUNT(*) as count FROM review_cases", conn
            ).iloc[0]['count']
            
            # Pending cases
            pending_cases = pd.read_sql_query(
                "SELECT COUNT(*) as count FROM review_cases WHERE review_status = 'pending'", conn
            ).iloc[0]['count']
            
            # Model accuracy
            accuracy_data = pd.read_sql_query("""
                SELECT 
                    human_classification,
                    ensemble_prediction,
                    COUNT(*) as count
                FROM review_cases 
                WHERE review_status = 'completed'
                GROUP BY human_classification
            """, conn)
            
            # Review turnaround time
            turnaround_data = pd.read_sql_query("""
                SELECT 
                    reviewer_id,
                    AVG((julianday(review_timestamp) - julianday(timestamp)) * 24) as avg_hours
                FROM review_cases 
                WHERE review_status = 'completed'
                GROUP BY reviewer_id
            """, conn)
            
            # Safety flags
            safety_data = pd.read_sql_query("""
                SELECT 
                    model_disagreement,
                    low_confidence,
                    safety_critical,
                    COUNT(*) as count
                FROM review_cases
                GROUP BY model_disagreement, low_confidence, safety_critical
            """, conn)
            
            conn.close()
            
            return {
                'total_cases': total_cases,
                'pending_cases': pending_cases,
                'accuracy_data': accuracy_data,
                'turnaround_data': turnaround_data,
                'safety_data': safety_data
            }
            
        except Exception as e:
            logger.error(f"Failed to get analytics: {e}")
            return {}


def create_sample_cases():
    """Create sample cases for testing dashboard"""
    dashboard = ReviewDashboard()
    
    sample_cases = [
        ReviewCase(
            case_id="case_001",
            user_message="I'm struggling with these thoughts",
            conversation_context=[],
            timestamp=datetime.now() - timedelta(hours=2),
            primary_prediction={"classification": "moderate_risk", "confidence": 0.65},
            validator_prediction={"validation_result": "safe", "confidence_level": 0.70},
            intent_prediction={"intent_category": "emotional_support", "confidence_score": 0.75},
            ensemble_prediction={"classification": "moderate_risk", "confidence": 0.68},
            review_status="pending",
            model_disagreement=True,
            low_confidence=True,
            safety_critical=False
        ),
        ReviewCase(
            case_id="case_002", 
            user_message="This workload is killing me slowly",
            conversation_context=[],
            timestamp=datetime.now() - timedelta(hours=1),
            primary_prediction={"classification": "safe", "confidence": 0.72},
            validator_prediction={"validation_result": "moderate_risk", "confidence_level": 0.60},
            intent_prediction={"intent_category": "emotional_support", "confidence_score": 0.80},
            ensemble_prediction={"classification": "safe", "confidence": 0.66},
            review_status="pending",
            model_disagreement=True,
            low_confidence=True,
            safety_critical=False
        )
    ]
    
    for case in sample_cases:
        dashboard.add_review_case(case)


def main():
    """Main Streamlit dashboard interface"""
    st.set_page_config(
        page_title="TheraLoop Review Dashboard",
        page_icon="🧠",
        layout="wide"
    )
    
    st.title("🧠 TheraLoop Human Review Dashboard")
    st.markdown("**DSPy Model Validation and Continuous Learning**")
    
    # Initialize dashboard
    dashboard = ReviewDashboard()
    
    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Select Page", [
        "Review Queue",
        "Analytics",
        "Model Performance",
        "Settings"
    ])
    
    if page == "Review Queue":
        show_review_queue(dashboard)
    elif page == "Analytics":
        show_analytics(dashboard)
    elif page == "Model Performance":
        show_model_performance(dashboard)
    elif page == "Settings":
        show_settings(dashboard)


def show_review_queue(dashboard: ReviewDashboard):
    """Display pending review cases"""
    st.header("📋 Review Queue")
    
    # Get pending cases
    pending_cases = dashboard.get_pending_cases()
    
    if not pending_cases:
        st.info("No pending cases for review!")
        if st.button("Generate Sample Cases"):
            create_sample_cases()
            st.rerun()
        return
    
    st.write(f"**{len(pending_cases)} cases awaiting review**")
    
    # Case selection
    case_options = [f"{case.case_id}: {case.user_message[:50]}..." for case in pending_cases]
    selected_idx = st.selectbox("Select Case to Review", range(len(case_options)), 
                               format_func=lambda x: case_options[x])
    
    if selected_idx is not None:
        case = pending_cases[selected_idx]
        
        # Case details
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📝 Case Details")
            st.write(f"**Message:** {case.user_message}")
            st.write(f"**Timestamp:** {case.timestamp}")
            
            # Flags
            flags = []
            if case.model_disagreement:
                flags.append("🔄 Model Disagreement")
            if case.low_confidence:
                flags.append("⚠️ Low Confidence")
            if case.safety_critical:
                flags.append("🚨 Safety Critical")
            
            if flags:
                st.warning(" | ".join(flags))
        
        with col2:
            st.subheader("📊 Urgency Score")
            urgency = 0
            if case.safety_critical:
                urgency += 3
            if case.model_disagreement:
                urgency += 2
            if case.low_confidence:
                urgency += 1
            
            urgency_color = "red" if urgency >= 4 else "orange" if urgency >= 2 else "green"
            st.markdown(f"<h2 style='color: {urgency_color}'>{urgency}/6</h2>", unsafe_allow_html=True)
        
        # Model predictions
        st.subheader("🤖 Model Predictions")
        
        pred_col1, pred_col2, pred_col3 = st.columns(3)
        
        with pred_col1:
            st.write("**Primary Model**")
            st.json(case.primary_prediction)
        
        with pred_col2:
            st.write("**Validator Model**")
            st.json(case.validator_prediction)
        
        with pred_col3:
            st.write("**Ensemble Result**")
            st.json(case.ensemble_prediction)
        
        # Human review form
        st.subheader("👨‍⚕️ Clinical Review")
        
        reviewer_id = st.text_input("Reviewer ID", value="reviewer_001")
        
        human_classification = st.selectbox(
            "Human Classification",
            ["crisis", "moderate_risk", "safe"],
            index=1
        )
        
        human_confidence = st.slider(
            "Confidence Level",
            min_value=0.0,
            max_value=1.0,
            value=0.8,
            step=0.1
        )
        
        clinical_notes = st.text_area(
            "Clinical Notes",
            placeholder="Provide detailed reasoning for your classification..."
        )
        
        if st.button("Submit Review", type="primary"):
            dashboard.submit_review(
                case.case_id,
                reviewer_id,
                human_classification,
                human_confidence,
                clinical_notes
            )
            st.success("Review submitted successfully!")
            st.rerun()


def show_analytics(dashboard: ReviewDashboard):
    """Display review analytics"""
    st.header("📊 Review Analytics")
    
    analytics = dashboard.get_review_analytics()
    
    if not analytics:
        st.error("Unable to load analytics data")
        return
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Cases", analytics.get('total_cases', 0))
    
    with col2:
        st.metric("Pending Reviews", analytics.get('pending_cases', 0))
    
    with col3:
        completion_rate = (analytics.get('total_cases', 1) - analytics.get('pending_cases', 0)) / analytics.get('total_cases', 1) * 100
        st.metric("Completion Rate", f"{completion_rate:.1f}%")
    
    with col4:
        avg_turnaround = analytics.get('turnaround_data', pd.DataFrame())
        if not avg_turnaround.empty:
            avg_hours = avg_turnaround['avg_hours'].mean()
            st.metric("Avg Turnaround", f"{avg_hours:.1f}h")
        else:
            st.metric("Avg Turnaround", "N/A")
    
    # Charts
    if 'accuracy_data' in analytics and not analytics['accuracy_data'].empty:
        st.subheader("Model vs Human Classifications")
        fig = px.bar(analytics['accuracy_data'], x='human_classification', y='count',
                    title="Human Classification Distribution")
        st.plotly_chart(fig, use_container_width=True)


def show_model_performance(dashboard: ReviewDashboard):
    """Display model performance metrics"""
    st.header("🎯 Model Performance")
    
    # Model comparison
    st.subheader("Model Accuracy Comparison")
    
    # Mock performance data
    performance_data = pd.DataFrame({
        'Model': ['Primary GEPA', 'Validator', 'Intent Classifier', 'Ensemble'],
        'Accuracy': [0.85, 0.82, 0.88, 0.91],
        'Precision': [0.83, 0.80, 0.85, 0.89],
        'Recall': [0.87, 0.84, 0.90, 0.93]
    })
    
    fig = px.bar(performance_data, x='Model', y=['Accuracy', 'Precision', 'Recall'],
                barmode='group', title="Model Performance Metrics")
    st.plotly_chart(fig, use_container_width=True)
    
    # Confidence calibration
    st.subheader("Confidence Calibration")
    
    # Mock calibration data
    calibration_data = pd.DataFrame({
        'Predicted_Confidence': [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
        'Actual_Accuracy': [0.05, 0.15, 0.25, 0.42, 0.48, 0.65, 0.72, 0.85, 0.92]
    })
    
    fig = px.line(calibration_data, x='Predicted_Confidence', y='Actual_Accuracy',
                 title="Model Confidence Calibration")
    fig.add_shape(type="line", x0=0, x1=1, y0=0, y1=1, 
                 line=dict(dash="dash", color="red"))
    st.plotly_chart(fig, use_container_width=True)


def show_settings(dashboard: ReviewDashboard):
    """Display dashboard settings"""
    st.header("⚙️ Settings")
    
    st.subheader("Review Thresholds")
    
    confidence_threshold = st.slider(
        "Low Confidence Threshold",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.05,
        help="Cases below this confidence will be flagged for review"
    )
    
    disagreement_threshold = st.slider(
        "Model Disagreement Threshold",
        min_value=0.0,
        max_value=1.0,
        value=0.2,
        step=0.05,
        help="Cases with prediction differences above this will be flagged"
    )
    
    st.subheader("Notification Settings")
    
    email_notifications = st.checkbox("Email Notifications", value=True)
    slack_notifications = st.checkbox("Slack Notifications", value=False)
    
    if st.button("Save Settings"):
        st.success("Settings saved!")


if __name__ == "__main__":
    main()