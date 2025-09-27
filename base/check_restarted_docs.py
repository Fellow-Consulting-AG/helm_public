#!/usr/bin/env python3
"""
Check specific restarted documents progression
"""

import sys
import os
from datetime import datetime, timedelta

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.database import SessionLocal
from logger import get_logger

logger = get_logger()


def get_recent_restarted_documents(limit=10):
    """Get recently restarted documents to monitor their progression."""
    session = SessionLocal()
    try:
        query = """
        SELECT
            id,
            status,
            doc_type,
            filename,
            created_on,
            last_modified_on
        FROM documents
        WHERE status = 'RESTARTED'
        AND is_deleted = false
        ORDER BY last_modified_on DESC
        LIMIT :limit
        """

        result = session.execute(text(query), {"limit": limit})
        documents = []

        for row in result:
            documents.append(
                {
                    "id": str(row.id),
                    "status": row.status,
                    "doc_type": row.doc_type,
                    "filename": row.filename,
                    "created_on": (
                        row.created_on.isoformat() if row.created_on else None
                    ),
                    "last_modified_on": (
                        row.last_modified_on.isoformat()
                        if row.last_modified_on
                        else None
                    ),
                }
            )

        return documents
    finally:
        session.close()


def check_processing_progression():
    """Check documents that might be stuck in processing states."""
    session = SessionLocal()
    try:
        # Check for documents in processing states for more than 30 minutes
        cutoff_time = datetime.now() - timedelta(minutes=30)

        query = """
        SELECT
            status,
            COUNT(*) as count
        FROM documents
        WHERE last_modified_on < :cutoff_time
        AND status IN ('RESTARTED', 'running', 'validating', 'processing')
        AND is_deleted = false
        GROUP BY status
        ORDER BY count DESC
        """

        result = session.execute(text(query), {"cutoff_time": cutoff_time})
        stuck_counts = {row.status: row.count for row in result}

        return stuck_counts
    finally:
        session.close()


def main():
    print("=== Recent Restarted Documents Monitor ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Get recent restarted documents
    restarted_docs = get_recent_restarted_documents(10)
    print(f"Recent RESTARTED documents ({len(restarted_docs)}):")
    for doc in restarted_docs:
        print(
            f"  {doc['id'][:8]}... | {doc['status']} | {doc['doc_type']} | {doc['filename']}"
        )
    print()

    # Check for potentially stuck documents
    stuck_counts = check_processing_progression()
    if stuck_counts:
        print("=== Potentially Stuck Documents (>30min in processing state) ===")
        for status, count in stuck_counts.items():
            print(f"  {status}: {count}")
    else:
        print("=== No documents stuck in processing states ===")
    print()

    # Output document IDs for monitoring
    if restarted_docs:
        print("=== Document IDs for monitoring ===")
        doc_ids = [doc["id"] for doc in restarted_docs]
        print(" ".join(doc_ids))


if __name__ == "__main__":
    main()
