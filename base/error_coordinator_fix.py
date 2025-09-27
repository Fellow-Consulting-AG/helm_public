#!/usr/bin/env python3
"""
Error Coordinator Fix for Document Processing Failure
Implements immediate corrective action for document 0a05caa9-bbfb-471c-b364-93fc44f9c8b2
"""

import sys
import os
from datetime import datetime

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.database import SessionLocal
from constants import DocumentStatus, DocumentStatusProcessing
from logger import get_logger

logger = get_logger()


class ErrorCoordinatorFix:
    """Error coordinator fix implementation"""

    def __init__(self):
        self.target_document_id = "0a05caa9-bbfb-471c-b364-93fc44f9c8b2"

    def analyze_document_failure(self):
        """Analyze the specific failure details for the document"""
        session = SessionLocal()
        try:
            query = """
            SELECT
                id,
                status,
                filename,
                extracted_data,
                created_on,
                last_modified_on,
                org_id,
                celery_task_token
            FROM documents
            WHERE id = :doc_id
            """

            result = session.execute(text(query), {"doc_id": self.target_document_id})
            doc = result.fetchone()

            if not doc:
                return {"error": "Document not found"}

            analysis = {
                "document_id": str(doc.id),
                "current_status": doc.status,
                "filename": doc.filename,
                "last_modified": (
                    doc.last_modified_on.isoformat() if doc.last_modified_on else None
                ),
                "org_id": doc.org_id,
                "has_extracted_data": bool(doc.extracted_data),
                "celery_task_token": doc.celery_task_token,
            }

            # Analyze extracted_data for processing details
            if doc.extracted_data:
                extracted_data = doc.extracted_data
                if isinstance(extracted_data, dict):
                    analysis["processing_modules"] = extracted_data.get(
                        "processed_modules_list", []
                    )
                    analysis["time_logs"] = extracted_data.get("time_logs", [])
                    analysis["doc_type"] = extracted_data.get("doc_type")
                    analysis["extraction_type"] = extracted_data.get("extraction_type")

                    # Check if there are any error indicators
                    if "error" in extracted_data:
                        analysis["error_details"] = extracted_data["error"]
                    if "exception_message" in extracted_data:
                        analysis["exception_message"] = extracted_data[
                            "exception_message"
                        ]

            return analysis

        finally:
            session.close()

    def reset_document_status(self):
        """Reset document from ERROR to RESTARTED status for reprocessing"""
        session = SessionLocal()
        try:
            # First check current status
            check_query = """
            SELECT status, filename
            FROM documents
            WHERE id = :doc_id
            """

            result = session.execute(
                text(check_query), {"doc_id": self.target_document_id}
            )
            doc = result.fetchone()

            if not doc:
                return {"success": False, "error": "Document not found"}

            if doc.status != "error":
                return {
                    "success": False,
                    "error": f"Document is not in error status. Current status: {doc.status}",
                }

            # Reset to RESTARTED status
            update_query = """
            UPDATE documents
            SET
                status = 'RESTARTED',
                last_modified_on = NOW(),
                restart_allowed = true
            WHERE id = :doc_id
            """

            session.execute(text(update_query), {"doc_id": self.target_document_id})
            session.commit()

            logger.add_log(
                "info",
                "all",
                f"ERROR_COORDINATOR_FIX: Reset document {self.target_document_id} from ERROR to RESTARTED",
            )

            return {
                "success": True,
                "message": f"Document {self.target_document_id} reset from ERROR to RESTARTED",
                "filename": doc.filename,
            }

        except Exception as e:
            session.rollback()
            logger.add_log("error", "all", f"Failed to reset document status: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    def trigger_processing(self):
        """Trigger processing for the reset document"""
        try:
            # Use Celery task queue to trigger processing
            from ctasks.trigger_restarted_documents import trigger_restarted_documents

            # Queue the task using .delay() for proper execution
            result = trigger_restarted_documents.delay()

            logger.add_log(
                "info",
                "all",
                f"ERROR_COORDINATOR_FIX: Queued trigger_restarted_documents task for document {self.target_document_id}",
            )

            return {
                "success": True,
                "task_id": result.id,
                "message": "Processing task queued successfully",
            }

        except Exception as e:
            logger.add_log("error", "all", f"Failed to trigger processing: {str(e)}")
            return {"success": False, "error": str(e)}

    def monitor_progress(self, timeout_seconds=120):
        """Monitor document progress after restart"""
        session = SessionLocal()
        start_time = datetime.now()

        try:
            while (datetime.now() - start_time).total_seconds() < timeout_seconds:
                query = """
                SELECT status, last_modified_on
                FROM documents
                WHERE id = :doc_id
                """

                result = session.execute(
                    text(query), {"doc_id": self.target_document_id}
                )
                doc = result.fetchone()

                if doc:
                    status = doc.status
                    last_modified = doc.last_modified_on

                    print(f"Status: {status} | Last Modified: {last_modified}")

                    if status == "ready_for_validation":
                        return {
                            "success": True,
                            "final_status": status,
                            "message": "Document successfully processed to ready_for_validation",
                        }
                    elif status == "error":
                        return {
                            "success": False,
                            "final_status": status,
                            "message": "Document failed again during processing",
                        }

                # Wait before next check
                import time

                time.sleep(10)

            # Timeout reached
            return {
                "success": False,
                "message": f"Monitoring timeout after {timeout_seconds} seconds",
                "final_status": doc.status if doc else "unknown",
            }

        finally:
            session.close()

    def execute_full_recovery(self):
        """Execute full recovery process"""
        print("=== ERROR COORDINATOR RECOVERY EXECUTION ===")
        print(f"Target Document: {self.target_document_id}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()

        # Step 1: Analyze current failure
        print("Step 1: Analyzing document failure...")
        analysis = self.analyze_document_failure()

        if "error" in analysis:
            print(f"❌ Analysis failed: {analysis['error']}")
            return analysis

        print(f"✅ Current Status: {analysis['current_status']}")
        print(f"✅ Filename: {analysis['filename']}")
        print(f"✅ Processing Modules: {analysis.get('processing_modules', [])}")
        print()

        # Step 2: Reset status
        print("Step 2: Resetting document status from ERROR to RESTARTED...")
        reset_result = self.reset_document_status()

        if not reset_result.get("success"):
            print(f"❌ Reset failed: {reset_result['error']}")
            return reset_result

        print(f"✅ {reset_result['message']}")
        print()

        # Step 3: Trigger processing
        print("Step 3: Triggering document processing...")
        trigger_result = self.trigger_processing()

        if isinstance(trigger_result, dict) and not trigger_result.get("success", True):
            print(f"❌ Trigger failed: {trigger_result.get('error', 'Unknown error')}")
            return trigger_result

        print("✅ Processing triggered successfully")
        print()

        # Step 4: Monitor progress
        print("Step 4: Monitoring document progress (120 seconds)...")
        monitor_result = self.monitor_progress(120)

        print(f"✅ Monitoring complete: {monitor_result['message']}")

        return {
            "success": monitor_result.get("success", False),
            "analysis": analysis,
            "reset_result": reset_result,
            "trigger_result": trigger_result,
            "monitor_result": monitor_result,
            "final_status": monitor_result.get("final_status"),
            "timestamp": datetime.now().isoformat(),
        }


def main():
    """Execute error coordinator fix"""
    coordinator = ErrorCoordinatorFix()
    result = coordinator.execute_full_recovery()

    print("\n=== FINAL RECOVERY RESULTS ===")
    if result.get("success"):
        print("🎉 RECOVERY SUCCESSFUL!")
        print(f"Final Status: {result.get('final_status')}")
    else:
        print("❌ RECOVERY FAILED")
        print(f"Final Status: {result.get('final_status', 'unknown')}")

    return result


if __name__ == "__main__":
    main()
