#!/usr/bin/env python3
"""
Start Beats Tasks Worker
Start a Celery worker to handle beats-tasks queue (scheduled tasks)
"""

import subprocess
import sys
import os
from datetime import datetime


def start_beats_worker():
    """Start a Celery worker for beats-tasks queue."""
    print("🚀 STARTING BEATS TASKS WORKER")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Change to project directory
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Start Celery worker for beats-tasks queue
    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "celery_run",
        "worker",
        "-Q",
        "beats-tasks",
        "--loglevel=info",
        "--concurrency=1",
    ]

    print(f"Command: {' '.join(cmd)}")
    print("Starting worker for beats-tasks queue...")
    print(
        "This worker will process scheduled tasks including trigger_restarted_documents"
    )
    print()
    print("✅ Worker started! Check terminal for Celery logs.")
    print("📋 This worker will process the 605 stuck RESTARTED documents.")
    print("🔄 trigger_restarted_documents runs every 1 minute")
    print()
    print("To stop the worker, press Ctrl+C")
    print("=" * 50)

    # Start the worker process
    subprocess.run(cmd)


if __name__ == "__main__":
    start_beats_worker()
