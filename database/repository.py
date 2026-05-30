from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import StudentProfileRecord


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
