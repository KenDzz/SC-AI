from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    full_name: str
    role: str

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class FactoryOut(BaseModel):
    id: str
    name: str
    code: str
    timezone: str

    model_config = {"from_attributes": True}


class CameraIn(BaseModel):
    factory_id: str | None = None
    code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=200)
    area: str = Field(min_length=2, max_length=120)
    stream_type: str
    stream_url: str = ""
    enabled: bool = True
    ai_fps: int = Field(default=25, ge=1, le=30)
    assigned_worker: str | None = None
    multi_view: bool = False


class CameraUpdate(BaseModel):
    name: str | None = None
    area: str | None = None
    stream_type: str | None = None
    stream_url: str | None = None
    enabled: bool | None = None
    ai_fps: int | None = Field(default=None, ge=1, le=30)
    assigned_worker: str | None = None
    multi_view: bool | None = None


class CameraOut(BaseModel):
    id: str
    factory_id: str
    code: str
    name: str
    area: str
    stream_type: str
    stream_url: str | None
    enabled: bool
    ai_fps: int
    assigned_worker: str | None
    multi_view: bool = False
    status: str
    created_at: datetime
    updated_at: datetime


class ZoneIn(BaseModel):
    camera_id: str
    name: str = Field(min_length=2, max_length=200)
    zone_type: str
    polygon: list[list[float]]
    reference_id: str | None = None


class ZoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    polygon: list[list[float]] | None = None
    reference_id: str | None = None


class ZoneOut(BaseModel):
    id: str
    factory_id: str
    camera_id: str
    name: str
    zone_type: str
    polygon: list[list[float]]
    reference_key: str | None = None

    model_config = {"from_attributes": True}


class RuleIn(BaseModel):
    zone_id: str
    name: str = Field(min_length=2, max_length=200)
    event_type: str
    condition_type: str
    min_duration_ms: int = Field(ge=0, le=600000)
    cooldown_ms: int = Field(ge=0, le=86400000)
    grace_ms: int = Field(default=1000, ge=0, le=60000)
    severity: str
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: str | None = None
    event_type: str | None = None
    condition_type: str | None = None
    min_duration_ms: int | None = Field(default=None, ge=0, le=600000)
    cooldown_ms: int | None = Field(default=None, ge=0, le=86400000)
    grace_ms: int | None = Field(default=None, ge=0, le=60000)
    severity: str | None = None
    enabled: bool | None = None


class RuleOut(BaseModel):
    id: str
    factory_id: str
    camera_id: str
    zone_id: str
    zone_name: str | None = None
    camera_name: str | None = None
    name: str
    event_type: str
    condition_type: str
    min_duration_ms: int
    cooldown_ms: int
    grace_ms: int
    severity: str
    enabled: bool
    extensions: dict


class ReviewIn(BaseModel):
    comment: str = ""


class FeedbackOut(BaseModel):
    id: str
    decision: str
    comment: str
    user_name: str
    created_at: datetime


class IncidentOut(BaseModel):
    id: str
    factory_id: str
    camera_id: str
    camera_name: str | None = None
    zone_id: str | None
    zone_name: str | None = None
    rule_id: str | None
    rule_name: str | None = None
    event_type: str
    severity: str
    track_id: str | None
    confidence: float | None
    started_at: datetime
    ended_at: datetime | None
    status: str
    snapshot_uri: str | None
    clip_uri: str | None
    model_name: str | None
    model_version: str | None
    ai_mode: str | None
    created_at: datetime
    updated_at: datetime


class IncidentPage(BaseModel):
    items: list[IncidentOut]
    total: int


class ModelOut(BaseModel):
    id: str
    name: str
    version: str
    model_type: str
    status: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentCreate(BaseModel):
    factory_id: str
    camera_id: str
    zone_id: str
    rule_id: str
    event_type: str
    severity: str
    track_id: str
    confidence: float = 0
    started_at: datetime
    model_name: str | None = None
    model_version: str | None = None
    ai_mode: str = "DEMO"
    snapshot_base64: str | None = None
    crop_base64: str | None = None


class IncidentClose(BaseModel):
    ended_at: datetime


class HeartbeatIn(BaseModel):
    status: str
    frames_processed: int = 0
    dropped_frames: int = 0
    inference_ms: float = 0
    detections: int = 0
    ai_fps: float = 0
    ai_mode: str = "DEMO"
    source_state: str = ""
    tracks: list[dict] = []
    zones: list[dict] = []
