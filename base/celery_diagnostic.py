#!/usr/bin/env python3
"""
Celery Diagnostic Tool
Check Celery task queue status and worker health
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


def check_celery_task_status():
    """Check Celery task status and queue health."""
    session = SessionLocal()
    try:
        # Check if celery_taskmeta table exists and get recent task status
        query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'celery_taskmeta'
        ) as table_exists
        """

        result = session.execute(text(query))
        table_exists = result.scalar()

        if not table_exists:
            return {"error": "celery_taskmeta table not found"}

        # Get recent task statistics
        recent_cutoff = datetime.now() - timedelta(hours=1)

        query = """
        SELECT
            status,
            COUNT(*) as count
        FROM celery_taskmeta
        WHERE date_done >= :cutoff
        GROUP BY status
        ORDER BY count DESC
        """

        result = session.execute(text(query), {"cutoff": recent_cutoff})
        recent_tasks = {row.status: row.count for row in result}

        # Get failed tasks in last hour
        query = """
        SELECT
            task_id,
            name,
            status,
            result,
            date_done
        FROM celery_taskmeta
        WHERE status = 'FAILURE'
        AND date_done >= :cutoff
        ORDER BY date_done DESC
        LIMIT 10
        """

        result = session.execute(text(query), {"cutoff": recent_cutoff})
        failed_tasks = []

        for row in result:
            failed_tasks.append(
                {
                    "task_id": row.task_id,
                    "name": row.name,
                    "status": row.status,
                    "result": row.result,
                    "date_done": row.date_done.isoformat() if row.date_done else None,
                }
            )

        return {
            "recent_task_counts": recent_tasks,
            "recent_failed_tasks": failed_tasks,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"error": f"Error checking Celery status: {str(e)}"}
    finally:
        session.close()


def check_document_processing_pipeline():
    """Check document processing pipeline health."""
    session = SessionLocal()
    try:
        # Check documents by status and when they were last modified
        status_age_query = """
        SELECT
            status,
            COUNT(*) as count,
            AVG(EXTRACT(EPOCH FROM (NOW() - last_modified_on))) as avg_age_seconds,
            MAX(EXTRACT(EPOCH FROM (NOW() - last_modified_on))) as max_age_seconds
        FROM documents
        WHERE is_deleted = false
        AND status IN ('RESTARTED', 'running', 'validating', 'processing', 'error')
        GROUP BY status
        ORDER BY avg_age_seconds DESC
        """

        result = session.execute(text(status_age_query))
        status_ages = []

        for row in result:
            status_ages.append(
                {
                    "status": row.status,
                    "count": row.count,
                    "avg_age_hours": (
                        round(row.avg_age_seconds / 3600, 2)
                        if row.avg_age_seconds
                        else 0
                    ),
                    "max_age_hours": (
                        round(row.max_age_seconds / 3600, 2)
                        if row.max_age_seconds
                        else 0
                    ),
                }
            )

        return {"status_ages": status_ages, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        return {"error": f"Error checking pipeline: {str(e)}"}
    finally:
        session.close()


def analyze_error_patterns():
    """Analyze error document patterns in detail."""
    session = SessionLocal()
    try:
        # Get recent error documents with extracted data analysis
        query = """
        SELECT
            id,
            doc_type,
            doc_source,
            filename,
            created_on,
            last_modified_on,
            CASE
                WHEN extracted_data IS NOT NULL THEN 'has_data'
                ELSE 'no_data'
            END as data_status
        FROM documents
        WHERE status = 'error'
        AND is_deleted = false
        AND last_modified_on >= NOW() - INTERVAL '24 hours'
        ORDER BY last_modified_on DESC
        LIMIT 20
        """

        result = session.execute(text(query))
        recent_errors = []

        for row in result:
            recent_errors.append(
                {
                    "id": str(row.id),
                    "doc_type": row.doc_type,
                    "doc_source": row.doc_source,
                    "filename": row.filename,
                    "created_on": (
                        row.created_on.isoformat() if row.created_on else None
                    ),
                    "last_modified_on": (
                        row.last_modified_on.isoformat()
                        if row.last_modified_on
                        else None
                    ),
                    "data_status": row.data_status,
                }
            )

        # Analyze error patterns
        from collections import Counter

        doc_type_errors = Counter(
            doc["doc_type"] for doc in recent_errors if doc["doc_type"]
        )
        source_errors = Counter(
            doc["doc_source"] for doc in recent_errors if doc["doc_source"]
        )
        data_status_errors = Counter(doc["data_status"] for doc in recent_errors)

        return {
            "recent_errors": recent_errors,
            "doc_type_patterns": dict(doc_type_errors),
            "source_patterns": dict(source_errors),
            "data_status_patterns": dict(data_status_errors),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"error": f"Error analyzing patterns: {str(e)}"}
    finally:
        session.close()


def main():
    print("=== Celery and Document Processing Diagnostic ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Check Celery task status
    print("=== Celery Task Status ===")
    celery_status = check_celery_task_status()
    if "error" in celery_status:
        print(f"Error: {celery_status['error']}")
    else:
        print("Recent task counts (last hour):")
        for status, count in celery_status["recent_task_counts"].items():
            print(f"  {status}: {count}")

        if celery_status["recent_failed_tasks"]:
            print("\nRecent failed tasks:")
            for task in celery_status["recent_failed_tasks"][:5]:
                print(
                    f"  {task['name']} | {task['task_id'][:8]}... | {task['result'][:100]}"
                )
    print()

    # Check document processing pipeline
    print("=== Document Processing Pipeline Health ===")
    pipeline_status = check_document_processing_pipeline()
    if "error" in pipeline_status:
        print(f"Error: {pipeline_status['error']}")
    else:
        print("Status ages analysis:")
        for status_info in pipeline_status["status_ages"]:
            print(
                f"  {status_info['status']}: {status_info['count']} docs, "
                f"avg age: {status_info['avg_age_hours']}h, "
                f"max age: {status_info['max_age_hours']}h"
            )
    print()

    # Analyze error patterns
    print("=== Error Pattern Analysis ===")
    error_patterns = analyze_error_patterns()
    if "error" in error_patterns:
        print(f"Error: {error_patterns['error']}")
    else:
        print(f"Recent errors (last 24h): {len(error_patterns['recent_errors'])}")
        print("Doc type patterns:", error_patterns["doc_type_patterns"])
        print("Source patterns:", error_patterns["source_patterns"])
        print("Data status patterns:", error_patterns["data_status_patterns"])


if __name__ == "__main__":
    main()
