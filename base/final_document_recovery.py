#!/usr/bin/env python3
"""
Final Document Recovery
Use the proper document processing workflow to restart the failed document
"""

import sys
import os
import asyncio
from datetime import datetime

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.database import SessionLocal
from database.dal.documents import DocumentsDAL
from database.models import Documents
from authenticator import UserAuthentication
from module.document_process import process_document_async
from constants import DocumentStatus, DocumentStatusProcessing
from logger import get_logger

logger = get_logger()


class FinalDocumentRecovery:
    """Final document recovery using proper processing workflow"""

    def __init__(self):
        self.target_document_id = "0a05caa9-bbfb-471c-b364-93fc44f9c8b2"

    def reset_document_to_restarted(self):
        """Reset document back to RESTARTED status"""
        session = SessionLocal()
        try:
            # Check current status
            check_query = """
            SELECT status, filename, org_id, created_by
            FROM documents
            WHERE id = :doc_id
            """

            result = session.execute(
                text(check_query), {"doc_id": self.target_document_id}
            )
            doc = result.fetchone()

            if not doc:
                return {"success": False, "error": "Document not found"}

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
                f"FINAL_RECOVERY: Reset document {self.target_document_id} to RESTARTED",
            )

            return {
                "success": True,
                "filename": doc.filename,
                "org_id": doc.org_id,
                "created_by": doc.created_by,
            }

        except Exception as e:
            session.rollback()
            logger.add_log("error", "all", f"Failed to reset document: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    async def process_document_properly(self):
        """Process document using the proper async workflow"""
        try:
            # Get document record
            doc_rec = DocumentsDAL.get_first_by_filters(
                [Documents.id == self.target_document_id]
            )

            if not doc_rec:
                return {"success": False, "error": "Document not found"}

            # Create a proper UserAuthentication object using the document's created_by
            # This is needed for the processing workflow
            class MockUserAuthentication:
                def __init__(self, user_id, org_id):
                    self.id = user_id
                    self.user_id = user_id
                    self.org_id = org_id

                def get_org_id(self):
                    return self.org_id

                def get_user_id(self):
                    return self.user_id

            mock_user = MockUserAuthentication(
                user_id=doc_rec.created_by or "system", org_id=doc_rec.org_id
            )

            print(
                f"🚀 Processing document {self.target_document_id[:8]}... with filename: {doc_rec.filename}"
            )

            # Set status to running
            doc_rec.status = DocumentStatusProcessing.RUNNING
            DocumentsDAL.save(doc_rec)

            logger.add_log(
                "info",
                "all",
                f"FINAL_RECOVERY: Started processing document {self.target_document_id}",
            )

            # Process the document using the main async processor
            result = await process_document_async(mock_user, doc_rec, checkpoint=0)

            if result:
                logger.add_log(
                    "info",
                    "all",
                    f"FINAL_RECOVERY: Document processing completed for {self.target_document_id}",
                )
                return {"success": True, "result": result}
            else:
                logger.add_log(
                    "error",
                    "all",
                    f"FINAL_RECOVERY: Document processing failed for {self.target_document_id}",
                )
                return {"success": False, "error": "Processing returned no result"}

        except Exception as e:
            logger.add_log(
                "error", "all", f"FINAL_RECOVERY: Processing exception: {str(e)}"
            )
            import traceback

            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def check_final_status(self):
        """Check the final status of the document"""
        session = SessionLocal()
        try:
            query = """
            SELECT status, last_modified_on
            FROM documents
            WHERE id = :doc_id
            """

            result = session.execute(text(query), {"doc_id": self.target_document_id})
            doc = result.fetchone()

            if doc:
                return {
                    "status": doc.status,
                    "last_modified": (
                        doc.last_modified_on.isoformat()
                        if doc.last_modified_on
                        else None
                    ),
                }
            else:
                return {"error": "Document not found"}

        finally:
            session.close()

    async def execute_final_recovery(self):
        """Execute the complete recovery process"""
        print("=== FINAL DOCUMENT RECOVERY ===")
        print(f"Target Document: {self.target_document_id}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()

        # Step 1: Reset to RESTARTED
        print("Step 1: Resetting document to RESTARTED status...")
        reset_result = self.reset_document_to_restarted()

        if not reset_result.get("success"):
            print(f"❌ Reset failed: {reset_result['error']}")
            return reset_result

        print(f"✅ Document reset successfully")
        print(f"   Filename: {reset_result['filename']}")
        print(f"   Org ID: {reset_result['org_id']}")
        print()

        # Step 2: Process using proper workflow
        print("Step 2: Processing document using proper async workflow...")
        process_result = await self.process_document_properly()

        if process_result.get("success"):
            print("✅ Document processing completed successfully")
        else:
            print(f"❌ Document processing failed: {process_result.get('error')}")

        # Step 3: Check final status
        print("\nStep 3: Checking final document status...")
        final_status = self.check_final_status()

        if "error" not in final_status:
            print(f"✅ Final Status: {final_status['status']}")
            print(f"   Last Modified: {final_status['last_modified']}")

            # Determine success based on final status
            success = final_status["status"] in ["ready_for_validation", "finished"]

            return {
                "success": success,
                "final_status": final_status["status"],
                "reset_result": reset_result,
                "process_result": process_result,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            print(f"❌ Could not check final status: {final_status['error']}")
            return {
                "success": False,
                "error": final_status["error"],
                "process_result": process_result,
            }


async def main():
    """Main async function"""
    recovery = FinalDocumentRecovery()
    result = await recovery.execute_final_recovery()

    print("\n=== FINAL RECOVERY RESULTS ===")
    if result.get("success"):
        print("🎉 RECOVERY SUCCESSFUL!")
        print(f"Final Status: {result.get('final_status')}")
    else:
        print("❌ RECOVERY FAILED")
        if "final_status" in result:
            print(f"Final Status: {result.get('final_status')}")
        if "error" in result:
            print(f"Error: {result['error']}")

    return result


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
