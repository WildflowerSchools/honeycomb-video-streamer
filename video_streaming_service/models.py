import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from pydantic import Field, BaseModel


# class VideoPart(BaseModel):
#     id: UUID = Field(default_factory=uuid4)
#     video_id: UUID
#     start_time: datetime.time
#     end_time: datetime.time
#     video_files: Optional[List[str]]
#     thumb_files: Optional[List[str]]
#     concatenated_video_url: str
#     concatenated_thumb_url: str


class Video(BaseModel):
    id: UUID = Field(default_factory=uuid4)
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
    id: UUID = Field(default_factory=uuid4)
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
    videos: Optional[List[VideoResponse]]


class PlaysetListResponse(BaseModel):
    playsets: Optional[List[PlaysetResponse]] = []


class Classroom(BaseModel):
    id: UUID
    name: str


class ClassroomResponse(BaseModel):
    id: UUID
    name: str
    playsets: Optional[List[Playset]]


class ClassroomListResponse(BaseModel):
    classrooms: Optional[List[ClassroomResponse]] = []
