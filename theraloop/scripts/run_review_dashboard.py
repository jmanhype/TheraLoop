#!/usr/bin/env python3
"""
Launch Human Review Dashboard
============================
Streamlit app for human-in-the-loop validation of DSPy predictions.

Usage:
    python scripts/run_review_dashboard.py
    
Then open: http://localhost:8501
"""

import os
import sys
import subprocess

# Add theraloop to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def main():
    """Launch the review dashboard"""
    dashboard_path = os.path.join(
        os.path.dirname(__file__), 
        "..", 
        "theraloop", 
        "serving", 
        "human_review_dashboard.py"
    )
    
    print("🧠 Starting TheraLoop Human Review Dashboard...")
    print("📱 Dashboard will be available at: http://localhost:8501")
    print("⚠️  Press Ctrl+C to stop the dashboard")
    
    try:
        subprocess.run([
            "streamlit", "run", dashboard_path,
            "--server.port", "8501",
            "--server.address", "0.0.0.0",
            "--theme.base", "light"
        ])
    except KeyboardInterrupt:
        print("\n✅ Dashboard stopped")
    except FileNotFoundError:
        print("❌ Streamlit not found. Install with: pip install streamlit")
    except Exception as e:
        print(f"❌ Failed to start dashboard: {e}")

if __name__ == "__main__":
    main()