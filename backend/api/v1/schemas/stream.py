from pydantic import BaseModel


class PlaybackSessionResponse(BaseModel):
    play_session_id: str
    item_id: str


class ProgressReportRequest(BaseModel):
    play_session_id: str
    position_seconds: float
    is_paused: bool = False


class StopReportRequest(BaseModel):
    play_session_id: str
    position_seconds: float
