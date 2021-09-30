import os

from cachetools.func import ttl_cache
from sqlalchemy import create_engine, select
from sqlalchemy import MetaData, Column, Table, String, ForeignKey, Date, Time
from sqlalchemy.dialects.postgresql import UUID
from fastapi import HTTPException
from wf_fastapi_auth0.wf_permissions import check_requests, AuthRequest

from .models import ClassroomList, Classroom, ClassroomResponse, Playset, PlaysetResponse, Video


engine = create_engine(os.environ.get("DATABASE_URI"))

metadata = MetaData()
classrooms = Table('classroom', metadata,
                   Column('id', UUID(), primary_key=True),
                   Column('name', String(16), nullable=False),
                   )

videos = Table('video', metadata,
               Column('id', UUID(), primary_key=True, nullable=False),
               Column('playset_id', UUID(), ForeignKey("playset.id"), nullable=False),
               Column('device_id', UUID(), nullable=True),
               Column('device_name', String(), nullable=True),
               Column('preview_url', String(), nullable=True),
               Column('preview_thumbnail_url', String(), nullable=True),
               Column('url', String(), nullable=True),
               )

playsets = Table('playset', metadata,
                 Column('id', UUID(), primary_key=True, nullable=False),
                 Column('classroom_id', UUID(), ForeignKey("classroom.id"), nullable=False),
                 Column('name', String(), nullable=True),
                 Column('date', Date(), nullable=True),
                 Column('start_time', Time(), nullable=True),
                 Column('end_time', Time(), nullable=True),
                 )


metadata.create_all(engine)


async def get_allowed_classrooms(subject):
    conn = engine.connect()
    result = ClassroomList()
    all_classrooms = []
    result.classrooms = []
    s = select(classrooms.c.id, classrooms.c.name)
    results = conn.execute(s)
    for row in results:
        c = Classroom(**row)
        all_classrooms.append(c)
    perm_check = await check_requests([AuthRequest(sub=subject[0], dom=subject[1], obj=f"{c.id}:videos", act="read") for c in all_classrooms])
    for i, c in enumerate(perm_check):
        if c["allow"]:
            result.classrooms.append(all_classrooms[i])
    return result


@ttl_cache(300)
def get_classroom(classroom_id):
    conn = engine.connect()
    classroom = conn.execute(select(classrooms).where(classrooms.c.id == classroom_id))
    if classroom is None:
        raise HTTPException(status_code=404, detail="not_found")
    response = ClassroomResponse(**classroom.first())
    response.playsets = []
    plays = conn.execute(select(playsets).where(playsets.c.classroom_id == classroom_id))
    for row in plays:
        response.playsets.append(Playset(**row))
    return response


@ttl_cache(300)
def get_playset(classroom_id, playset_date):
    conn = engine.connect()
    playset = conn.execute(
        select(playsets).where(
            playsets.c.classroom_id == classroom_id,
            playsets.c.date == playset_date))
    if playset is None:
        raise HTTPException(status_code=401, detail="not_found")
    response = PlaysetResponse(**playset.first())
    response.videos = []
    vids = conn.execute(select(videos).where(videos.c.playset_id == str(response.id)))
    for row in vids:
        response.videos.append(Video(**row))
    return response
