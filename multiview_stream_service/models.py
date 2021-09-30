import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from pydantic import Field, BaseModel


class Classroom(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str


class ClassroomList(BaseModel):
    classrooms: Optional[List[Classroom]] = []


class Video(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    device_id: Optional[str]
    device_name: Optional[str]
    url: Optional[str]
    preview_url: Optional[str]
    preview_thumbnail_url: Optional[str]


class Playset(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    classroom_id: UUID
    name: str
    date: datetime.date
    start_time: datetime.time
    end_time: datetime.time


class PlaysetResponse(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    videos: Optional[List[Video]]


class ClassroomResponse(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    playsets: Optional[List[Playset]]
