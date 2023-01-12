import os
from typing import List, Optional

from cachetools.func import ttl_cache
from sqlalchemy import create_engine, select, insert, delete, or_
from sqlalchemy import MetaData, Column, Table, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from wf_fastapi_auth0.wf_permissions import check_requests, AuthRequest

from .models import (
    ClassroomList,
    Classroom,
    ClassroomResponse,
    Playset,
    PlaysetListResponse,
    PlaysetResponse,
    Video,
    VideoResponse,
)


engine = create_engine(os.environ.get("DATABASE_URI"))

metadata = MetaData()
classrooms_tbl = Table(
    "classroom",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("name", String(16), nullable=False),
)

playsets_tbl = Table(
    "playset",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("classroom_id", UUID(as_uuid=True), ForeignKey("classroom.id"), nullable=False),
    Column("name", String(), nullable=True),
    Column("start_time", DateTime(), nullable=True),
    Column("end_time", DateTime(), nullable=True),
)

videos_tbl = Table(
    "video",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
    Column("playset_id", UUID(as_uuid=True), ForeignKey("playset.id", ondelete="CASCADE"), nullable=False),
    Column("device_id", UUID(as_uuid=True), nullable=True),
    Column("device_name", String(), nullable=True),
    Column("preview_url", String(), nullable=True),
    Column("preview_thumbnail_url", String(), nullable=True),
    Column("url", String(), nullable=True),
)


class PermissionException(Exception):
    pass


# video_parts = Table(
#     "video_part",
#     metadata,
#     Column("id", UUID(), primary_key=True, nullable=False),
#     Column("video_id", UUID(), ForeignKey("video.id"), nullable=False),
#     Column("start_time", Time(), nullable=False),
#     Column("end_time", Time(), nullable=False),
#     Column("video_files", ARRAY(str), nullable=False),
#     Column("thumb_files", ARRAY(str), nullable=False),
#     Column("concatenated_video_url", String(), nullable=False),
#     Column("concatenated_thumb_url", String(), nullable=False),
# )


metadata.create_all(engine)


class Handle(object):
    # For unrestricted acccess, use:
    #    perm_subject="wildflower-robots@wildflower-tech.org"
    #    perm_domain="wildflowerschools.org"
    def __init__(self, perm_subject, perm_domain):
        self.connection = engine.connect()

        self.permission_subject = perm_subject
        self.permission_domain = perm_domain

    def __del__(self):
        self.connection.close()

    async def has_read_permission(self, environment_id):
        resp = await check_requests(
            [
                AuthRequest(
                    sub=self.permission_subject, dom=self.permission_domain, obj=f"{environment_id}:videos", act="read"
                )
            ]
        )
        return resp[0]["allow"]

    async def has_write_permission(self, environment_id):
        resp = await check_requests(
            [
                AuthRequest(
                    sub=self.permission_subject, dom=self.permission_domain, obj=f"{environment_id}:videos", act="write"
                )
            ]
        )
        return resp[0]["allow"]

    async def has_delete_permission(self, environment_id):
        resp = await check_requests(
            [
                AuthRequest(
                    sub=self.permission_subject,
                    dom=self.permission_domain,
                    obj=f"{environment_id}:videos",
                    act="delete",
                )
            ]
        )
        return resp[0]["allow"]

    async def get_classrooms(self) -> ClassroomList:
        result = ClassroomList()
        result.classrooms = []

        s = select(classrooms_tbl.c.id, classrooms_tbl.c.name)
        results = self.connection.execute(s)
        for row in results:
            c = Classroom(**row)
            if await self.has_read_permission(c.id):
                result.classrooms.append(c)

        return result

    async def create_classroom(self, classroom: Classroom) -> ClassroomResponse:
        if not await self.has_write_permission(classroom.id):
            raise PermissionException(f"User does not have write permission for classroom '{classroom.id}'")

        response = self.connection.execute(
            insert(classrooms_tbl).values(id=classroom.id, name=classroom.name).returning(classrooms_tbl)
        )
        return ClassroomResponse(**dict(response.first()))

    @ttl_cache(300)
    async def get_classroom(self, classroom_id) -> Optional[ClassroomResponse]:
        if not await self.has_read_permission(classroom_id):
            raise PermissionException(f"User does not have read permission for classroom '{classroom_id}'")

        classroom_records = self.connection.execute(select(classrooms_tbl).where(classrooms_tbl.c.id == classroom_id))

        if classroom_records is None or classroom_records.rowcount == 0:
            return None

        response = ClassroomResponse(**classroom_records.first())
        response.playsets = []
        playset_records = self.connection.execute(
            select(playsets_tbl).where(playsets_tbl.c.classroom_id == classroom_id)
        )
        for playset_record in playset_records:
            response.playsets.append(Playset(**dict(playset_record)))
        return response

    async def create_playset(self, playset: Playset) -> PlaysetResponse:
        if not await self.has_write_permission(playset.classroom_id):
            raise PermissionException(f"User does not have read permission for classroom '{playset.classroom_id}'")

        response = self.connection.execute(
            insert(playsets_tbl)
            .values(
                id=playset.id,
                classroom_id=playset.classroom_id,
                name=playset.name,
                start_time=playset.start_time,
                end_time=playset.end_time,
            )
            .returning(playsets_tbl)
        )
        return PlaysetResponse(**dict(response.first()))

    @ttl_cache(300)
    async def get_playsets(self, classroom_id) -> Optional[PlaysetListResponse]:
        if not await self.has_read_permission(classroom_id):
            raise PermissionException(f"User does not have read permission for classroom '{classroom_id}'")

        playset_records = self.connection.execute(
            select(playsets_tbl).where(playsets_tbl.c.classroom_id == classroom_id)
        )
        if playset_records is None or playset_records.rowcount == 0:
            return None

        playsets_response = PlaysetListResponse
        for playset_record in playset_records:
            response = PlaysetResponse(**dict(playset_record))
            response.videos = []
            video_records = self.connection.execute(
                select(videos_tbl).where(videos_tbl.c.playset_id == str(response.id))
            )
            for video_record in video_records:
                response.videos.append(Video(**video_record))

            playsets_response.playsets.append(response)

        return playsets_response

    @ttl_cache(300)
    async def get_playset(self, playset_id) -> Optional[PlaysetResponse]:
        playset_records = self.connection.execute(select(playsets_tbl).where(playsets_tbl.c.id == playset_id))
        if playset_records is None or playset_records.rowcount == 0:
            return None

        playset_response = PlaysetResponse(**playset_records.first())

        if not await self.has_read_permission(playset_response.classroom_id):
            raise PermissionException(
                f"User does not have read permission for classroom '{playset_response.classroom_id}'"
            )

        playset_response.videos = []
        video_records = self.connection.execute(
            select(videos_tbl).where(videos_tbl.c.playset_id == str(playset_response.id))
        )
        for video_record in video_records:
            playset_response.videos.append(VideoResponse(**dict(video_record)))

        return playset_response

    @ttl_cache(300)
    async def get_playset_by_name(self, classroom_id, playset_name) -> Optional[PlaysetResponse]:
        if not await self.has_read_permission(classroom_id):
            raise PermissionException(f"User does not have read permission for classroom '{classroom_id}'")

        playset_records = self.connection.execute(
            select(playsets_tbl).where(
                playsets_tbl.c.classroom_id == classroom_id, or_(playsets_tbl.c.name == playset_name)
            )
        )
        if playset_records is None or playset_records.rowcount == 0:
            return None

        playset_response = PlaysetResponse(**playset_records.first())
        playset_response.videos = []
        video_records = self.connection.execute(
            select(videos_tbl).where(videos_tbl.c.playset_id == str(playset_response.id))
        )
        for video_record in video_records:
            playset_response.videos.append(VideoResponse(**dict(video_record)))

        return playset_response

    @ttl_cache(300)
    async def get_playsets_by_date(self, classroom_id, playset_date) -> Optional[PlaysetListResponse]:
        if not await self.has_read_permission(classroom_id):
            raise PermissionException(f"User does not have read permission for classroom '{classroom_id}'")

        playset_records = self.connection.execute(
            select(playsets_tbl).where(
                playsets_tbl.c.classroom_id == classroom_id,
                or_(playsets_tbl.c.start_time == playset_date, playsets_tbl.c.end_time == playset_date),
            )
        )
        if playset_records is None or playset_records.rowcount == 0:
            return None

        playsets_response = PlaysetListResponse
        for playset_record in playset_records:
            response = PlaysetResponse(playset_record)
            response.videos = []
            video_records = self.connection.execute(
                select(videos_tbl).where(videos_tbl.c.playset_id == str(response.id))
            )
            for video_record in video_records:
                response.videos.append(Video(**video_record))

            playsets_response.playsets.append(response)

        return playsets_response

    async def delete_playset(self, playset_id) -> bool:
        playset = await self.get_playset(playset_id)

        if not await self.has_delete_permission(playset.classroom_id):
            raise PermissionException(f"User does not have delete permission for classroom '{playset.classroom_id}'")

        response = self.connection.execute(delete(playsets_tbl).where(playsets_tbl.c.id == playset_id))
        return response.rowcount > 0

    async def create_video(self, video: Video) -> VideoResponse:
        playset = await self.get_playset(video.playset_id)

        if not await self.has_write_permission(playset.classroom_id):
            raise PermissionException(f"User does not have write permission for classroom '{playset.classroom_id}'")

        response = self.connection.execute(
            insert(videos_tbl)
            .values(
                id=video.id,
                playset_id=video.playset_id,
                device_id=video.device_id,
                device_name=video.device_name,
                preview_url=video.preview_url,
                preview_thumbnail_url=video.preview_thumbnail_url,
                url=video.url,
            )
            .returning(videos_tbl)
        )
        return VideoResponse(**dict(response.first()))
