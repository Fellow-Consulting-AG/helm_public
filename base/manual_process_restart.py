#!/usr/bin/env python3
"""
Manual Process Restart
Manually process documents in RESTARTED status by calling the core logic directly
"""

import sys
import os
from datetime import datetime

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.database import SessionLocal
from database import db_helper as dbh
from logger import get_logger

logger = get_logger()


def manual_process_restarted_documents():
    """Manually process restarted documents by calling core processing logic directly"""
    try:
        print("🚀 MANUAL PROCESS: Processing documents in RESTARTED status")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()

        session = SessionLocal()
        try:
            # Find documents in restarted status
            query = """
                SELECT
                    id,
                    status,
                    filename,
                    org_id,
                    created_by,
                    celery_task_token,
                    created_on,
                    last_modified_on
                FROM documents
                WHERE
                    (status = 'restarted' OR status = 'RESTARTED')
                    AND is_deleted = false
                ORDER BY last_modified_on ASC
                LIMIT 10
            """

            restarted_documents = dbh.execute_query(query, return_json=False)

            print(f"📊 Found {len(restarted_documents)} documents in RESTARTED status")

            if len(restarted_documents) == 0:
                print("✅ No documents in RESTARTED status to process")
                return {"success": True, "documents_processed": 0}

            documents_processed = 0

            for doc_row in restarted_documents:
                doc_id = str(doc_row["id"])
                filename = doc_row.get("filename", "unknown")
                org_id = doc_row["org_id"]

                print(f"🚀 Processing DocID: {doc_id[:8]}..., Filename: {filename}")

                try:
                    # Import the document processor
                    from module.document_process import document_processor

                    # Set document status to running before processing
                    update_query = """
                    UPDATE documents
                    SET
                        status = 'running',
                        last_modified_on = NOW()
                    WHERE id = :doc_id
                    """

                    session.execute(text(update_query), {"doc_id": doc_id})
                    session.commit()

                    print(f"  ✅ Set status to running for {doc_id[:8]}...")

                    # Process the document using the document processor
                    # This is the core processing logic that handles document workflow
                    result = document_processor.process_document(
                        doc_id=doc_id, org_id=org_id, force_restart=True
                    )

                    if result and result.get("success"):
                        print(f"  ✅ Successfully processed {doc_id[:8]}...")
                        documents_processed += 1
                    else:
                        print(f"  ❌ Processing failed for {doc_id[:8]}...")
                        print(f"     Error: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    print(f"  ❌ Exception processing {doc_id[:8]}...: {str(e)}")
                    logger.add_log(
                        "error", "all", f"Failed to process document {doc_id}: {str(e)}"
                    )

                    # Set status back to error on failure
                    try:
                        error_query = """
                        UPDATE documents
                        SET
                            status = 'error',
                            last_modified_on = NOW()
                        WHERE id = :doc_id
                        """

                        session.execute(text(error_query), {"doc_id": doc_id})
                        session.commit()
                    except Exception as update_error:
                        print(
                            f"  ❌ Failed to update error status: {str(update_error)}"
                        )

            print(f"\n=== PROCESSING COMPLETE ===")
            print(f"Documents processed: {documents_processed}")

            return {
                "success": True,
                "documents_processed": documents_processed,
                "total_found": len(restarted_documents),
            }

        finally:
            session.close()

    except Exception as e:
        logger.add_log("error", "all", f"Manual process failed: {str(e)}")
        print(f"❌ ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        return {"success": False, "error": str(e)}


def check_status_before_and_after():
    """Check document status before and after manual processing"""
    from document_monitor import DocumentMonitor

    monitor = DocumentMonitor()

    print("=== STATUS BEFORE MANUAL PROCESSING ===")
    before_status = monitor.get_document_status_counts()
    for status, count in before_status.items():
        if status in ["RESTARTED", "error", "running", "ready_for_validation"]:
            print(f"{status}: {count}")
    print()

    # Execute manual processing
    result = manual_process_restarted_documents()

    print("\n=== STATUS AFTER MANUAL PROCESSING ===")
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
