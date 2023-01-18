import os
from typing import Optional

from cachetools.func import ttl_cache
from sqlalchemy import create_engine, select, insert, delete, or_
from sqlalchemy.orm import sessionmaker
from wf_fastapi_auth0.wf_permissions import check_requests, AuthRequest

from . import schema
from .models import (
    ClassroomListResponse,
    Classroom,
    ClassroomResponse,
    Playset,
    PlaysetListResponse,
    PlaysetResponse,
    Video,
    VideoResponse,
)


class Database:
    __instance = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, uri=os.environ.get("DATABASE_URI")):
        self.engine = create_engine(uri)
        self._create_schema()

        self._session_maker = self._create_session_maker()

    def _create_schema(self):
        schema.metadata.create_all(self.engine)

    def _create_session_maker(self):
        return sessionmaker(autocommit=True, autoflush=False, bind=self.engine)

    def get_session(self):
        db = self._session_maker()
        try:
            yield db
        finally:
            db.close()


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


class Handle:
    # For unrestricted acccess, use:
    #    perm_subject="wildflower-robots@wildflower-tech.org"
    #    perm_domain="wildflowerschools.org"
    def __init__(self, db_session, perm_subject, perm_domain):
        self.db_session = db_session

        self.permission_subject = perm_subject
        self.permission_domain = perm_domain

    # def __del__(self):
    #     self.connection.close()

    async def has_read_permission(self, environment_id) -> bool:
        resp = await check_requests(
            [
                AuthRequest(
                    sub=self.permission_subject, dom=self.permission_domain, obj=f"{environment_id}:videos", act="read"
                )
            ]
        )
        return resp[0]["allow"]

    async def has_write_permission(self, environment_id) -> bool:
        resp = await check_requests(
            [
                AuthRequest(
                    sub=self.permission_subject, dom=self.permission_domain, obj=f"{environment_id}:videos", act="write"
                )
            ]
        )
        return resp[0]["allow"]

    async def has_delete_permission(self, environment_id) -> bool:
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

    async def get_classrooms(self) -> ClassroomListResponse:
        result = ClassroomListResponse()
        result.classrooms = []

        s = select(schema.classrooms_tbl.c.id, schema.classrooms_tbl.c.name)
        results = self.db_session.execute(s)
        for row in results:
            c = ClassroomResponse(**row)
            if await self.has_read_permission(c.id):
                result.classrooms.append(c)

        return result

    async def create_classroom(self, classroom: Classroom) -> ClassroomResponse:
        if not await self.has_write_permission(classroom.id):
            raise PermissionException(f"User does not have write permission for classroom '{classroom.id}'")

        response = self.db_session.execute(
            insert(schema.classrooms_tbl).values(id=classroom.id, name=classroom.name).returning(schema.classrooms_tbl)
        )
        return ClassroomResponse(**dict(response.first()))

    @ttl_cache(300)
    async def get_classroom(self, classroom_id) -> Optional[ClassroomResponse]:
        if not await self.has_read_permission(classroom_id):
            raise PermissionException(f"User does not have read permission for classroom '{classroom_id}'")

        classroom_records = self.db_session.execute(
            select(schema.classrooms_tbl).where(schema.classrooms_tbl.c.id == classroom_id)
        )

        if classroom_records is None or classroom_records.rowcount == 0:
            return None

        response = ClassroomResponse(**classroom_records.first())
        response.playsets = []
        playset_records = self.db_session.execute(
            select(schema.playsets_tbl).where(schema.playsets_tbl.c.classroom_id == classroom_id)
        )
        for playset_record in playset_records:
            response.playsets.append(Playset(**dict(playset_record)))
        return response

    async def create_playset(self, playset: Playset) -> PlaysetResponse:
        if not await self.has_write_permission(playset.classroom_id):
            raise PermissionException(f"User does not have read permission for classroom '{playset.classroom_id}'")

        response = self.db_session.execute(
            insert(schema.playsets_tbl)
            .values(
                id=playset.id,
                classroom_id=playset.classroom_id,
                name=playset.name,
                start_time=playset.start_time,
                end_time=playset.end_time,
            )
            .returning(schema.playsets_tbl)
        )
        return PlaysetResponse(**dict(response.first()))

    @ttl_cache(300)
    async def get_playsets(self, classroom_id) -> Optional[PlaysetListResponse]:
        if not await self.has_read_permission(classroom_id):
            raise PermissionException(f"User does not have read permission for classroom '{classroom_id}'")

        playset_records = self.db_session.execute(
            select(schema.playsets_tbl).where(schema.playsets_tbl.c.classroom_id == classroom_id)
        )
        if playset_records is None or playset_records.rowcount == 0:
            return None

        playsets_response = PlaysetListResponse()
        for playset_record in playset_records:
            response = PlaysetResponse(**dict(playset_record))
            response.videos = []
            video_records = self.db_session.execute(
                select(schema.videos_tbl).where(schema.videos_tbl.c.playset_id == str(response.id))
            )
            for video_record in video_records:
                response.videos.append(Video(**video_record))

            playsets_response.playsets.append(response)

        return playsets_response

    @ttl_cache(300)
    async def get_playset(self, playset_id) -> Optional[PlaysetResponse]:
        playset_records = self.db_session.execute(
            select(schema.playsets_tbl).where(schema.playsets_tbl.c.id == playset_id)
        )
        if playset_records is None or playset_records.rowcount == 0:
            return None

        playset_response = PlaysetResponse(**playset_records.first())

        if not await self.has_read_permission(playset_response.classroom_id):
            raise PermissionException(
                f"User does not have read permission for classroom '{playset_response.classroom_id}'"
            )

        playset_response.videos = []
        video_records = self.db_session.execute(
            select(schema.videos_tbl).where(schema.videos_tbl.c.playset_id == str(playset_response.id))
        )
        for video_record in video_records:
            playset_response.videos.append(VideoResponse(**dict(video_record)))

        return playset_response

    @ttl_cache(300)
    async def get_playset_by_name(self, classroom_id, playset_name) -> Optional[PlaysetResponse]:
        if not await self.has_read_permission(classroom_id):
            raise PermissionException(f"User does not have read permission for classroom '{classroom_id}'")

        playset_records = self.db_session.execute(
            select(schema.playsets_tbl).where(
                schema.playsets_tbl.c.classroom_id == classroom_id, or_(schema.playsets_tbl.c.name == playset_name)
            )
        )
        if playset_records is None or playset_records.rowcount == 0:
            return None

        playset_response = PlaysetResponse(**playset_records.first())
        playset_response.videos = []
        video_records = self.db_session.execute(
            select(schema.videos_tbl).where(schema.videos_tbl.c.playset_id == str(playset_response.id))
        )
        for video_record in video_records:
            playset_response.videos.append(VideoResponse(**dict(video_record)))

        return playset_response

    @ttl_cache(300)
    async def get_playsets_by_date(self, classroom_id, playset_date) -> Optional[PlaysetListResponse]:
        if not await self.has_read_permission(classroom_id):
            raise PermissionException(f"User does not have read permission for classroom '{classroom_id}'")

        playset_records = self.db_session.execute(
            select(schema.playsets_tbl).where(
                schema.playsets_tbl.c.classroom_id == classroom_id,
                or_(schema.playsets_tbl.c.start_time == playset_date, schema.playsets_tbl.c.end_time == playset_date),
            )
        )
        if playset_records is None or playset_records.rowcount == 0:
            return None

        playsets_response = PlaysetListResponse()
        for playset_record in playset_records:
            response = PlaysetResponse(playset_record)
            response.videos = []
            video_records = self.db_session.execute(
                select(schema.videos_tbl).where(schema.videos_tbl.c.playset_id == str(response.id))
            )
            for video_record in video_records:
                response.videos.append(Video(**video_record))

            playsets_response.playsets.append(response)

        return playsets_response

    async def delete_playset(self, playset_id) -> bool:
        playset = await self.get_playset(playset_id)

        if not await self.has_delete_permission(playset.classroom_id):
            raise PermissionException(f"User does not have delete permission for classroom '{playset.classroom_id}'")

        response = self.db_session.execute(delete(schema.playsets_tbl).where(schema.playsets_tbl.c.id == playset_id))
        return response.rowcount > 0

    async def create_video(self, video: Video) -> VideoResponse:
        playset = await self.get_playset(video.playset_id)

        if not await self.has_write_permission(playset.classroom_id):
            raise PermissionException(f"User does not have write permission for classroom '{playset.classroom_id}'")

        response = self.db_session.execute(
            insert(schema.videos_tbl)
            .values(
                id=video.id,
                playset_id=video.playset_id,
                device_id=video.device_id,
                device_name=video.device_name,
                preview_url=video.preview_url,
                preview_thumbnail_url=video.preview_thumbnail_url,
                url=video.url,
            )
            .returning(schema.videos_tbl)
        )
        return VideoResponse(**dict(response.first()))
