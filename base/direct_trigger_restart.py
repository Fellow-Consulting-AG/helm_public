#!/usr/bin/env python3
"""
Direct Trigger for Restarted Documents
Directly execute the trigger_restarted_documents task without Celery queueing.
"""

import sys
import os
from datetime import datetime

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import get_logger

logger = get_logger()


def direct_trigger_restarted_documents():
    """Directly call the main trigger function with proper database injection."""
    try:
        print(
            "🚀 DIRECT TRIGGER: Executing trigger_restarted_documents function directly"
        )
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()

        # Import the function and run it with proper setup
        from ctasks.trigger_restarted_documents import trigger_restarted_documents
        from database.database import SessionLocal

        # Create a mock Celery request object
        class MockRequest:
            def __init__(self):
                self.id = f"direct-trigger-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Mock self object
        class MockSelf:
            def __init__(self):
                self.request = MockRequest()

        # Get database session manually since we're bypassing db_inject
        db = SessionLocal()
        try:
            # Call the function with the database session
            mock_self = MockSelf()
            result = trigger_restarted_documents(mock_self, db=db)

            print("=== DIRECT TRIGGER RESULTS ===")
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

        finally:
            db.close()

    except Exception as e:
        logger.add_log("error", "all", f"Direct trigger failed: {str(e)}")
        print(f"❌ ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        return {"status": "failed", "error": str(e)}


def check_status_before_and_after():
    """Check document status before and after direct trigger."""
    from document_monitor import DocumentMonitor

    monitor = DocumentMonitor()

    print("=== STATUS BEFORE DIRECT TRIGGER ===")
    before_status = monitor.get_document_status_counts()
    for status, count in before_status.items():
        if status in ["RESTARTED", "error", "running", "ready_for_validation"]:
            print(f"{status}: {count}")
    print()

    # Execute direct trigger
    result = direct_trigger_restarted_documents()

    # Wait a moment for any immediate changes
    import time

    time.sleep(2)

    print("\n=== STATUS AFTER DIRECT TRIGGER ===")
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
