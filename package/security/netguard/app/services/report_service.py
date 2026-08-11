"""报告导出服务 — CSV / JSON"""

import csv
import io
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.threat import ThreatRecord
from app.models.scan import ScanRecord
from app.models.protection import ProtectionEvent


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def export_threats(self, user_id: int, fmt: str = "csv") -> tuple[str, str]:
        """导出威胁记录，返回 (content, content_type)"""
        result = await self.db.execute(
            select(ThreatRecord)
            .where(ThreatRecord.user_id == user_id)
            .order_by(ThreatRecord.created_at.desc())
        )
        records = result.scalars().all()

        rows = [
            {
                "id": r.id,
                "target": r.target,
                "target_type": r.target_type,
                "is_malicious": r.is_malicious,
                "score": r.score,
                "categories": json.dumps(r.categories),
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]

        return self._format(rows, fmt, "threats")

    async def export_scans(self, user_id: int, fmt: str = "csv") -> tuple[str, str]:
        result = await self.db.execute(
            select(ScanRecord)
            .where(ScanRecord.user_id == user_id)
            .order_by(ScanRecord.created_at.desc())
        )
        records = result.scalars().all()

        rows = [
            {
                "id": r.id,
                "target": r.target,
                "scan_type": r.scan_type,
                "duration_ms": r.duration_ms,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]

        return self._format(rows, fmt, "scans")

    async def export_protection(self, user_id: int, fmt: str = "csv") -> tuple[str, str]:
        result = await self.db.execute(
            select(ProtectionEvent)
            .where(ProtectionEvent.user_id == user_id)
            .order_by(ProtectionEvent.created_at.desc())
        )
        records = result.scalars().all()

        rows = [
            {
                "id": r.id,
                "event_type": r.event_type,
                "source_ip": r.source_ip,
                "blocked": r.blocked,
                "action_taken": r.action_taken,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]

        return self._format(rows, fmt, "protection")

    def _format(self, rows: list[dict], fmt: str, name: str) -> tuple[str, str]:
        if fmt == "json":
            return json.dumps(rows, indent=2, ensure_ascii=False), "application/json"

        # CSV
        if not rows:
            return "", "text/csv"
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue(), "text/csv"
