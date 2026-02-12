import time
import uuid
import logging
from typing import Optional

from open_webui.env import SRC_LOG_LEVELS
from open_webui.internal.db import get_db
from open_webui.models.base import Base

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, String, Text

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

####################
# CodeSession DB Schema
####################


class CodeSession(Base):
    __tablename__ = "code_session"

    id = Column(String, primary_key=True)
    user_id = Column(String)
    workspace_path = Column(Text)
    
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class CodeSessionModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    workspace_path: str
    
    created_at: int  # timestamp in epoch
    updated_at: int  # timestamp in epoch


####################
# Forms
####################


class CodeSessionResponse(BaseModel):
    id: str
    user_id: str
    workspace_path: str
    created_at: int
    updated_at: int


####################
# CodeSessions DB Functions
####################


class CodeSessions:
    def insert_new_session(self, user_id: str, workspace_path: str) -> Optional[CodeSessionModel]:
        with get_db() as db:
            id = str(uuid.uuid4())
            session = CodeSessionModel(
                **{
                    "id": id,
                    "user_id": user_id,
                    "workspace_path": workspace_path,
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
            )

            result = CodeSession(**session.model_dump())
            db.add(result)
            db.commit()
            db.refresh(result)

            if result:
                return CodeSessionModel.model_validate(result)
            else:
                return None

    def get_session_by_id(self, id: str) -> Optional[CodeSessionModel]:
        try:
            with get_db() as db:
                session = db.query(CodeSession).filter_by(id=id).first()
                return CodeSessionModel.model_validate(session) if session else None
        except Exception:
            return None

    def get_sessions_by_user_id(self, user_id: str) -> list[CodeSessionModel]:
        with get_db() as db:
            sessions = (
                db.query(CodeSession)
                .filter_by(user_id=user_id)
                .order_by(CodeSession.created_at.desc())
                .all()
            )
            return [CodeSessionModel.model_validate(session) for session in sessions]

    def delete_session_by_id(self, id: str) -> bool:
        try:
            with get_db() as db:
                db.query(CodeSession).filter_by(id=id).delete()
                db.commit()
                return True
        except Exception:
            return False
