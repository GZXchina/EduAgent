from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import EvaluationReport, LearningBehaviorRecord, LearningResource, StudentProfileRecord


class ProfileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_session(self, session_id: str) -> StudentProfileRecord | None:
        stmt = (
            select(StudentProfileRecord)
            .where(StudentProfileRecord.session_id == session_id)
            .order_by(StudentProfileRecord.updated_at.desc())
        )
        return self.db.scalars(stmt).first()

    def upsert(self, session_id: str, profile: dict) -> StudentProfileRecord:
        row = self.get_by_session(session_id)
        payload = json.dumps(profile, ensure_ascii=False)
        now = datetime.utcnow()
        if row is None:
            row = StudentProfileRecord(session_id=session_id, profile_json=payload, updated_at=now)
            self.db.add(row)
        else:
            row.profile_json = payload
            row.updated_at = now
        self.db.commit()
        self.db.refresh(row)
        return row

    @staticmethod
    def to_dict(row: StudentProfileRecord) -> dict:
        try:
            return json.loads(row.profile_json)
        except json.JSONDecodeError:
            return {"raw": row.profile_json}


class ResourceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save_resource(self, session_id: str, resource_type: str, content: dict) -> LearningResource:
        payload = json.dumps(content, ensure_ascii=False)
        row = LearningResource(
            session_id=session_id,
            resource_type=resource_type,
            content_json=payload,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_resources_by_session(self, session_id: str) -> list[LearningResource]:
        stmt = (
            select(LearningResource)
            .where(LearningResource.session_id == session_id)
            .order_by(LearningResource.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_resources_by_type(self, session_id: str, resource_type: str) -> list[LearningResource]:
        stmt = (
            select(LearningResource)
            .where(
                LearningResource.session_id == session_id,
                LearningResource.resource_type == resource_type,
            )
            .order_by(LearningResource.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def save_evaluation_report(self, session_id: str, report: dict, score: float | None = None) -> EvaluationReport:
        payload = json.dumps(report, ensure_ascii=False)
        row = EvaluationReport(
            session_id=session_id,
            report_json=payload,
            score=score,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_evaluation_reports(self, session_id: str) -> list[EvaluationReport]:
        stmt = (
            select(EvaluationReport)
            .where(EvaluationReport.session_id == session_id)
            .order_by(EvaluationReport.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    @staticmethod
    def resource_to_dict(row: LearningResource) -> dict:
        try:
            return json.loads(row.content_json)
        except json.JSONDecodeError:
            return {"raw": row.content_json}

    def save_behavior(
        self, session_id: str, action: str, detail: dict, duration_minutes: int = 0
    ) -> LearningBehaviorRecord:
        """持久化一条学习行为记录。"""
        payload = json.dumps(detail, ensure_ascii=False)
        row = LearningBehaviorRecord(
            session_id=session_id,
            action=action,
            detail_json=payload,
            duration_minutes=duration_minutes,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_behaviors_by_session(self, session_id: str) -> list[LearningBehaviorRecord]:
        """获取某会话的全部学习行为记录。"""
        stmt = (
            select(LearningBehaviorRecord)
            .where(LearningBehaviorRecord.session_id == session_id)
            .order_by(LearningBehaviorRecord.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def aggregate_behaviors(self, session_id: str) -> dict:
        """聚合某会话的学习行为数据，用于评估报告。"""
        behaviors = self.get_behaviors_by_session(session_id)
        if not behaviors:
            return {
                "total_actions": 0,
                "total_duration_minutes": 0,
                "action_counts": {},
                "resource_usage": {},
                "quiz_results": [],
                "knowledge_mastery": {},
            }

        action_counts: dict[str, int] = {}
        total_duration = 0
        resource_usage: dict[str, int] = {}
        quiz_results: list[dict] = []
        knowledge_mastery: dict[str, float] = {}

        for row in behaviors:
            action_counts[row.action] = action_counts.get(row.action, 0) + 1
            total_duration += row.duration_minutes

            try:
                detail = json.loads(row.detail_json)
            except json.JSONDecodeError:
                detail = {}

            # 资源浏览计数
            if row.action == "resource_view" and "resource_type" in detail:
                rt = detail["resource_type"]
                resource_usage[rt] = resource_usage.get(rt, 0) + 1

            # 练习结果
            if row.action == "quiz" and "correct" in detail:
                quiz_results.append({
                    "correct": detail["correct"],
                    "question": detail.get("question", ""),
                    "knowledge_point": detail.get("knowledge_point", ""),
                })

            # 知识掌握度上报
            if row.action == "knowledge_mastery" and "topic" in detail:
                knowledge_mastery[detail["topic"]] = detail.get("score", 0.0)

        return {
            "total_actions": len(behaviors),
            "total_duration_minutes": total_duration,
            "action_counts": action_counts,
            "resource_usage": resource_usage,
            "quiz_results": quiz_results,
            "knowledge_mastery": knowledge_mastery,
        }

    @staticmethod
    def report_to_dict(row: EvaluationReport) -> dict:
        try:
            data = json.loads(row.report_json)
            data["score"] = row.score
            data["created_at"] = row.created_at.isoformat() if row.created_at else None
            return data
        except json.JSONDecodeError:
            return {"raw": row.report_json, "score": row.score}
