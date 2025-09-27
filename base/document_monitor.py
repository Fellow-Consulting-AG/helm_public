#!/usr/bin/env python3
"""
Document Status Monitor
Monitor progression of restarted documents and analyze error patterns.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from collections import Counter
import uuid

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker
from database.database import engine, SessionLocal
from database.models.models import Documents
from logger import get_logger

logger = get_logger()


class DocumentMonitor:
    """Monitor document status progression and analyze patterns."""

    def __init__(self):
        self.engine = engine

    def get_document_status_counts(self, org_id: str = None) -> Dict[str, int]:
        """Get current status counts for all documents."""
        session = SessionLocal()
        try:
            query = """
            SELECT status, COUNT(*) as count
            FROM documents
            WHERE is_deleted = false
            """

            params = {}
            if org_id:
                query += " AND org_id = :org_id"
                params["org_id"] = org_id

            query += " GROUP BY status ORDER BY count DESC"

            result = session.execute(text(query), params)
            return {row.status: row.count for row in result}
        finally:
            session.close()

    def check_restarted_documents_progression(self, document_ids: List[str]) -> Dict:
        """Check status progression of specific restarted documents."""
        if not document_ids:
            return {"error": "No document IDs provided"}

        session = SessionLocal()
        try:
            # Convert string IDs to UUID format for query
            uuid_list = []
            for doc_id in document_ids:
                try:
                    if isinstance(doc_id, str):
                        uuid_list.append(str(uuid.UUID(doc_id)))
                    else:
                        uuid_list.append(str(doc_id))
                except ValueError:
                    logger.add_log("warning", "all", f"Invalid UUID format: {doc_id}")
                    continue

            if not uuid_list:
                return {"error": "No valid UUIDs found"}

            # Create placeholders for IN clause
            placeholders = ",".join([f":id_{i}" for i in range(len(uuid_list))])
            params = {f"id_{i}": uuid_val for i, uuid_val in enumerate(uuid_list)}

            query = f"""
            SELECT
                id,
                status,
                doc_type,
                filename,
                created_on,
                last_modified_on,
                timestamp_for_validation
            FROM documents
            WHERE id::text IN ({placeholders})
            AND is_deleted = false
            ORDER BY last_modified_on DESC
            """

            result = session.execute(text(query), params)
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
                        "timestamp_for_validation": (
                            row.timestamp_for_validation.isoformat()
                            if row.timestamp_for_validation
                            else None
                        ),
                    }
                )

            # Analyze status distribution
            status_counts = Counter(doc["status"] for doc in documents)

            return {
                "total_documents": len(documents),
                "status_distribution": dict(status_counts),
                "documents": documents,
                "timestamp": datetime.now().isoformat(),
            }
        finally:
            session.close()

    def analyze_error_documents(self, limit: int = 50, org_id: str = None) -> Dict:
        """Analyze recent error documents for patterns."""
        session = SessionLocal()
        try:
            query = """
            SELECT
                id,
                status,
                doc_type,
                filename,
                doc_source,
                created_on,
                last_modified_on,
                extracted_data
            FROM documents
            WHERE status = 'error'
            AND is_deleted = false
            """

            params = {}
            if org_id:
                query += " AND org_id = :org_id"
                params["org_id"] = org_id

            query += " ORDER BY last_modified_on DESC LIMIT :limit"
            params["limit"] = limit

            result = session.execute(text(query), params)
            error_docs = []

            for row in result:
                error_docs.append(
                    {
                        "id": str(row.id),
                        "status": row.status,
                        "doc_type": row.doc_type,
                        "filename": row.filename,
                        "doc_source": row.doc_source,
                        "created_on": (
                            row.created_on.isoformat() if row.created_on else None
                        ),
                        "last_modified_on": (
                            row.last_modified_on.isoformat()
                            if row.last_modified_on
                            else None
                        ),
                        "has_extracted_data": bool(row.extracted_data),
                    }
                )

            # Analyze patterns
            doc_type_counts = Counter(
                doc["doc_type"] for doc in error_docs if doc["doc_type"]
            )
            doc_source_counts = Counter(
                doc["doc_source"] for doc in error_docs if doc["doc_source"]
            )

            return {
                "total_error_documents": len(error_docs),
                "doc_type_distribution": dict(doc_type_counts),
                "doc_source_distribution": dict(doc_source_counts),
                "recent_errors": error_docs[:10],  # Show first 10 for details
                "timestamp": datetime.now().isoformat(),
            }
        finally:
            session.close()

    def get_recent_status_changes(self, hours: int = 24, org_id: str = None) -> Dict:
        """Get documents with recent status changes."""
        session = SessionLocal()
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            query = """
            SELECT
                id,
                status,
                doc_type,
                filename,
                created_on,
                last_modified_on
            FROM documents
            WHERE last_modified_on >= :cutoff_time
            AND is_deleted = false
            """

            params = {"cutoff_time": cutoff_time}
            if org_id:
                query += " AND org_id = :org_id"
                params["org_id"] = org_id

            query += " ORDER BY last_modified_on DESC"

            result = session.execute(text(query), params)
            recent_changes = []

            for row in result:
                recent_changes.append(
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

            # Analyze status distribution
            status_counts = Counter(doc["status"] for doc in recent_changes)

            return {
                "total_recent_changes": len(recent_changes),
                "status_distribution": dict(status_counts),
                "recent_changes": recent_changes[:20],  # Show first 20
                "hours_analyzed": hours,
                "timestamp": datetime.now().isoformat(),
            }
        finally:
            session.close()


def main():
    """Main monitoring function."""
    monitor = DocumentMonitor()

    print("=== Document Status Monitor ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Overall status counts
    print("=== Overall Status Distribution ===")
    status_counts = monitor.get_document_status_counts()
    for status, count in status_counts.items():
        print(f"{status}: {count}")
    print()

    # Recent changes in last 24 hours
    print("=== Recent Status Changes (24 hours) ===")
    recent_changes = monitor.get_recent_status_changes(hours=24)
    print(f"Total recent changes: {recent_changes['total_recent_changes']}")
    print("Status distribution:")
    for status, count in recent_changes["status_distribution"].items():
        print(f"  {status}: {count}")
    print()

    # Error document analysis
    print("=== Error Document Analysis ===")
    error_analysis = monitor.analyze_error_documents(limit=50)
    print(f"Total error documents: {error_analysis['total_error_documents']}")
    print("Doc type distribution:")
    for doc_type, count in error_analysis["doc_type_distribution"].items():
        print(f"  {doc_type}: {count}")
    print("Doc source distribution:")
    for doc_source, count in error_analysis["doc_source_distribution"].items():
        print(f"  {doc_source}: {count}")
    print()

    # Check for specific restarted documents if provided as arguments
    if len(sys.argv) > 1:
        document_ids = sys.argv[1:]
        print(f"=== Checking Specific Documents ({len(document_ids)} IDs) ===")
        restart_progress = monitor.check_restarted_documents_progression(document_ids)

        if "error" in restart_progress:
            print(f"Error: {restart_progress['error']}")
        else:
            print(f"Total documents found: {restart_progress['total_documents']}")
            print("Status distribution:")
            for status, count in restart_progress["status_distribution"].items():
                print(f"  {status}: {count}")

            print("\nDocument details:")
            for doc in restart_progress["documents"]:
                print(
                    f"  {doc['id'][:8]}... | {doc['status']} | {doc['doc_type']} | {doc['filename']}"
                )


if __name__ == "__main__":
    main()
