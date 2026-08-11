"""统计服务"""

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.protection import ProtectionEvent
from app.models.scan import ScanRecord
from app.models.threat import ThreatRecord
from app.models.traffic import TrafficAnalysisRecord


class StatsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard(self, user_id: int, tier: str) -> dict:
        """获取用户仪表盘统计"""
        # 威胁查询统计
        threat_q = select(
            func.count().label("total"),
            func.sum(
                case((ThreatRecord.is_malicious == True, 1), else_=0)  # noqa: E712
            ).label("malicious"),
        ).where(ThreatRecord.user_id == user_id)

        # 扫描统计
        scan_q = select(func.count()).where(ScanRecord.user_id == user_id)

        # 流量分析统计
        traffic_q = select(func.count()).where(
            TrafficAnalysisRecord.user_id == user_id
        )

        # 防护事件统计
        protection_q = select(
            func.count().label("total"),
            func.sum(
                case((ProtectionEvent.blocked == True, 1), else_=0)  # noqa: E712
            ).label("blocked"),
        ).where(ProtectionEvent.user_id == user_id)

        threat_r = (await self.db.execute(threat_q)).one()
        scan_r = (await self.db.execute(scan_q)).scalar()
        traffic_r = (await self.db.execute(traffic_q)).scalar()
        protection_r = (await self.db.execute(protection_q)).one()

        return {
            "user_id": user_id,
            "tier": tier,
            "stats": {
                "threat_lookups": threat_r.total or 0,
                "malicious_detections": threat_r.malicious or 0,
                "scans": scan_r or 0,
                "traffic_analyses": traffic_r or 0,
                "protection_events": protection_r.total or 0,
                "blocked_attacks": protection_r.blocked or 0,
            },
            "limits": {"tier": tier},
        }
