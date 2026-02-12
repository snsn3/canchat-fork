import logging
import time
from typing import Optional

from open_webui.internal.db import get_db
from open_webui.env import SRC_LOG_LEVELS
from open_webui.models.base import Base
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, Integer, String

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

####################
# Artifacts DB Schema
####################


class Artifact(Base):
    __tablename__ = "artifact"
    id = Column(String, primary_key=True)
    user_id = Column(String)
    filename = Column(String)
    mime_type = Column(String)
    relative_path = Column(String)
    size = Column(Integer)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class ArtifactModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    filename: str
    mime_type: str
    relative_path: str
    size: int
    created_at: int  # timestamp in epoch
    updated_at: int  # timestamp in epoch


####################
# Forms
####################


class ArtifactForm(BaseModel):
    id: str
    filename: str
    mime_type: str
    relative_path: str
    size: int


class ArtifactResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    mime_type: str
    size: int
    created_at: int  # timestamp in epoch
    updated_at: int  # timestamp in epoch
    url: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ArtifactsTable:
    def insert_new_artifact(
        self, user_id: str, form_data: ArtifactForm
    ) -> Optional[ArtifactModel]:
        with get_db() as db:
            artifact = ArtifactModel(
                **{
                    **form_data.model_dump(),
                    "user_id": user_id,
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
            )

            try:
                result = Artifact(**artifact.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return ArtifactModel.model_validate(result)
                else:
                    return None
            except Exception as e:
                log.error(f"Error creating artifact: {e}")
                return None

    def get_artifact_by_id(self, id: str) -> Optional[ArtifactModel]:
        with get_db() as db:
            try:
                artifact = db.get(Artifact, id)
                return ArtifactModel.model_validate(artifact) if artifact else None
            except Exception:
                return None

    def get_artifacts_by_user_id(self, user_id: str) -> list[ArtifactModel]:
        with get_db() as db:
            return [
                ArtifactModel.model_validate(artifact)
                for artifact in db.query(Artifact)
                .filter(Artifact.user_id == user_id)
                .all()
            ]

    def get_artifacts(self) -> list[ArtifactModel]:
        with get_db() as db:
            return [
                ArtifactModel.model_validate(artifact)
                for artifact in db.query(Artifact).all()
            ]

    def delete_artifact_by_id(self, id: str) -> bool:
        with get_db() as db:
            try:
                artifact = db.get(Artifact, id)
                if artifact:
                    db.delete(artifact)
                    db.commit()
                    return True
                return False
            except Exception as e:
                log.error(f"Error deleting artifact: {e}")
                return False


Artifacts = ArtifactsTable()
