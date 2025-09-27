#!/usr/bin/env python3
"""
Manual Trigger for Restarted Documents
Manually execute the trigger_restarted_documents task to process stuck documents.
"""

import sys
import os
from datetime import datetime

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import get_logger

logger = get_logger()


def manual_trigger_restarted_documents():
    """Manually trigger the restarted documents processing."""
    try:
        print("🚀 MANUAL TRIGGER: Starting trigger_restarted_documents task")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()

        # Import and run the task using apply() to run synchronously
        from ctasks.trigger_restarted_documents import (
            trigger_restarted_documents_enhanced,
        )

        # Execute the task synchronously using .apply()
        result = trigger_restarted_documents_enhanced.apply()

        # Get the actual result
        if hasattr(result, "result"):
            result = result.result
        elif hasattr(result, "get"):
            result = result.get()

        print("=== MANUAL TRIGGER RESULTS ===")
        if isinstance(result, dict):
            print(f"Status: {result.get('status', 'Unknown')}")
            print(f"Documents processed: {result.get('documents_processed', 0)}")
            print(f"Documents queued: {result.get('documents_queued', 0)}")
            print(f"Errors: {result.get('errors', 0)}")
            if "error_details" in result:
                print(f"Error details: {result['error_details']}")
        else:
            print(f"Result: {result}")

        return result

    except Exception as e:
        logger.add_log("error", "all", f"Manual trigger failed: {str(e)}")
        print(f"❌ ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        return {"status": "failed", "error": str(e)}


def check_status_before_and_after():
    """Check document status before and after manual trigger."""
    from document_monitor import DocumentMonitor

    monitor = DocumentMonitor()

    print("=== STATUS BEFORE MANUAL TRIGGER ===")
    before_status = monitor.get_document_status_counts()
    for status, count in before_status.items():
        if status in ["RESTARTED", "error", "running", "ready_for_validation"]:
            print(f"{status}: {count}")
    print()

    # Execute manual trigger
    result = manual_trigger_restarted_documents()

    print("\n=== STATUS AFTER MANUAL TRIGGER ===")
    after_status = monitor.get_document_status_counts()
    for status, count in after_status.items():
        if status in ["RESTARTED", "error", "running", "ready_for_validation"]:
            print(f"{status}: {count}")
    print()

    # Calculate changes
    print("=== STATUS CHANGES ===")
    for status in ["RESTARTED", "error", "running", "ready_for_validation"]:
        before_count = before_status.get(status, 0)
        after_count = after_status.get(status, 0)
        change = after_count - before_count
        if change != 0:
            print(f"{status}: {before_count} → {after_count} (change: {change:+d})")

    return result


if __name__ == "__main__":
    check_status_before_and_after()
