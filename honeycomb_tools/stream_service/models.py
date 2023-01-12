import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from pydantic import Field, BaseModel


class Video(BaseModel):
    playset_id: UUID
    device_id: Optional[UUID]
    device_name: Optional[str]
    url: Optional[str]
    preview_url: Optional[str]
    preview_thumbnail_url: Optional[str]


class VideoResponse(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    playset_id: UUID
    device_id: UUID
    device_name: str
    url: str
    preview_url: str
    preview_thumbnail_url: str


class Playset(BaseModel):
    classroom_id: UUID
    name: str
    start_time: datetime.datetime
    end_time: datetime.datetime


class PlaysetResponse(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    classroom_id: UUID
    name: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    videos: Optional[List[Video]]


class PlaysetListResponse(BaseModel):
    playsets: List[PlaysetResponse]

class Classroom(BaseModel):
    id: UUID
    name: str


class ClassroomResponse(BaseModel):
    id: UUID
    name: str
    playsets: Optional[List[Playset]]


class ClassroomList(BaseModel):
    classrooms: Optional[List[Classroom]] = []
