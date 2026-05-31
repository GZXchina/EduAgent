from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import EvaluationReport, LearningResource, StudentProfileRecord


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

    @staticmethod
    def report_to_dict(row: EvaluationReport) -> dict:
        try:
            data = json.loads(row.report_json)
            data["score"] = row.score
            data["created_at"] = row.created_at.isoformat() if row.created_at else None
            return data
        except json.JSONDecodeError:
            return {"raw": row.report_json, "score": row.score}
