import os

from cachetools.func import ttl_cache
from sqlalchemy import create_engine, select
from sqlalchemy import MetaData, Column, Table, String, ForeignKey, UniqueConstraint, Date, Time
from sqlalchemy.dialects.postgresql import UUID
from fastapi import HTTPException

from .models import ClassroomList, Classroom, ClassroomResponse, Playset, PlaysetResponse, Video


engine = create_engine(os.environ.get("DATABASE_URI"))

metadata = MetaData()
classrooms = Table('classroom', metadata,
    Column('id', UUID(), primary_key=True),
    Column('name', String(16), nullable=False),
)

global_allows = Table('global_allow', metadata,
    Column('id', UUID(), primary_key=True),
    Column('email', String(128), nullable=False),
)

classroom_allows = Table('classroom_allow', metadata,
    Column('classroom_id', UUID(), ForeignKey("classroom.id"), nullable=False),
    Column('email', String(128), nullable=False),
    UniqueConstraint('classroom_id', 'email', name='classroom_allow_unique'),
)

classroom_owners = Table('classroom_owner', metadata,
    Column('classroom_id', UUID(), ForeignKey("classroom.id"), nullable=False),
    Column('email', String(128), nullable=False),
    UniqueConstraint('classroom_id', 'email', name='classroom_owner_unique'),
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


@ttl_cache(300)
def is_global_user(user_email):
    conn = engine.connect()
    s = select(global_allows).where(global_allows.c.email==user_email)
    results = conn.execute(s)
    return results is not None


def get_allowed_classrooms(user_email):
    conn = engine.connect()
    result = ClassroomList()
    result.classrooms = []
    s = select(classrooms.c.id, classrooms.c.name)
    if not is_global_user(user_email):
        own = [row.classroom_id for row in conn.execute(classroom_owners.select().where(classroom_owners.c.email==user_email))]
        allowed = [row.classroom_id for row in conn.execute(classroom_allows.select().where(classroom_allows.c.email==user_email))]
        s = s.where(classrooms.c.id.in_(own + allowed))
    results = conn.execute(s)
    for row in results:
        c = Classroom(**row)
        c.owners = [row.email for row in conn.execute(classroom_owners.select().where(classroom_owners.c.classroom_id==str(c.id)))]
        c.allows = [row.email for row in conn.execute(classroom_allows.select().where(classroom_allows.c.classroom_id==str(c.id)))]
        result.classrooms.append(c)
    return result


def classroom_allowed(classroom_id, user_email):
    conn = engine.connect()
    if not is_global_user(user_email):
        own = conn.execute(select(classroom_owners).where(classroom_owners.c.email==user_email, classroom_owners.classroom_id==classroom_id))
        if own is None:
            allow = conn.execute(select(classroom_allows).where(classroom_allows.c.email==user_email, classroom_allows.classroom_id==classroom_id))
            if allow is None:
                raise HTTPException(status_code=401, detail="unauthorized")
    return True


def get_classroom(classroom_id):
    conn = engine.connect()
    classroom = conn.execute(select(classrooms).where(classrooms.c.id==classroom_id))
    if classroom is None:
        raise HTTPException(status_code=404, detail="not_found")
    response = ClassroomResponse(**classroom.first())
    response.playsets = []
    plays = conn.execute(select(playsets).where(playsets.c.classroom_id==classroom_id))
    for row in plays:
        response.playsets.append(Playset(**row))
    return response


def get_playset(classroom_id, playset_date):
    conn = engine.connect()
    playset = conn.execute(select(playsets).where(playsets.c.classroom_id==classroom_id, playsets.c.date==playset_date))
    if playset is None:
        raise HTTPException(status_code=401, detail="not_found")
    response = PlaysetResponse(**playset.first())
    response.videos = []
    vids = conn.execute(select(videos).where(videos.c.playset_id==str(response.id)))
    for row in vids:
        response.videos.append(Video(**row))
    return response
