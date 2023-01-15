import logging
import os
from pathlib import Path
from typing import Optional

from cachetools.func import ttl_cache
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from wf_fastapi_auth0 import verify_token, get_subject_domain
from wf_fastapi_auth0.wf_permissions import AuthRequest, check_requests
from .models import (
    ClassroomListResponse,
    ClassroomResponse,
    PlaysetListResponse,
    PlaysetResponse,
    Classroom,
    Playset,
    Video,
    VideoResponse,
)

from .honeycomb_service import HoneycombClient
from .database import Database, Handle, PermissionException

router = APIRouter()
database = Database()
honeycomb_client = HoneycombClient()

STATIC_PATH = os.environ.get("STATIC_PATH", "./public/videos")


@ttl_cache(30)
async def can_read(perm_subject_domain: tuple = Depends(get_subject_domain)) -> bool:
    resp = await check_requests(
        [AuthRequest(sub=perm_subject_domain[0], dom=perm_subject_domain[1], obj="classroom:videos", act="read")]
    )
    return resp[0]["allow"]


@ttl_cache(30)
async def can_write(perm_subject_domain: tuple = Depends(get_subject_domain)) -> bool:
    resp = await check_requests(
        [AuthRequest(sub=perm_subject_domain[0], dom=perm_subject_domain[1], obj="classroom:videos", act="write")]
    )
    return resp[0]["allow"]


@ttl_cache(30)
async def can_delete(perm_subject_domain: tuple = Depends(get_subject_domain)) -> bool:
    resp = await check_requests(
        [AuthRequest(sub=perm_subject_domain[0], dom=perm_subject_domain[1], obj="classroom:videos", act="delete")]
    )
    return resp[0]["allow"]


@router.get(
    "/videos/classrooms", dependencies=[Depends(verify_token), Depends(can_read)], response_model=ClassroomListResponse
)
async def load_classroom_list(
    perm_subject_domain: tuple = Depends(get_subject_domain), db_session=Depends(database.get_session)
) -> Optional[ClassroomListResponse]:
    try:
        db = Handle(db_session=db_session, perm_subject=perm_subject_domain[0], perm_domain=perm_subject_domain[1])
        return await db.get_classrooms()
    except PermissionException as e:
        logging.error(e)
        raise HTTPException(status_code=401, detail="not_allowed") from e


@router.get(
    "/videos/classrooms/{classroom_id}",
    dependencies=[Depends(verify_token), Depends(can_read)],
    response_model=ClassroomResponse,
)
async def load_classroom(
    classroom_id: str,
    perm_subject_domain: tuple = Depends(get_subject_domain),
    db_session=Depends(database.get_session),
) -> Optional[ClassroomResponse]:
    try:
        db = Handle(db_session=db_session, perm_subject=perm_subject_domain[0], perm_domain=perm_subject_domain[1])
        return await db.get_classroom(classroom_id)
    except PermissionException as e:
        logging.error(e)
        raise HTTPException(status_code=401, detail="not_allowed") from e


@router.get(
    "/videos/classrooms/{classroom_id}/playsets",
    dependencies=[Depends(verify_token), Depends(can_read)],
    response_model=PlaysetListResponse,
)
async def load_classroom_playsets(
    classroom_id: str,
    perm_subject_domain: tuple = Depends(get_subject_domain),
    db_session=Depends(database.get_session),
) -> Optional[PlaysetListResponse]:
    try:
        db = Handle(db_session=db_session, perm_subject=perm_subject_domain[0], perm_domain=perm_subject_domain[1])
        return await db.get_playsets(classroom_id)
    except PermissionException as e:
        logging.error(e)
        raise HTTPException(status_code=401, detail="not_allowed") from e


@router.get(
    "/videos/classrooms/{classroom_id}/playset_by_name/{name}",
    dependencies=[Depends(verify_token), Depends(can_read)],
    response_model=PlaysetResponse,
)
async def load_playset_by_name(
    classroom_id: str,
    name: str,
    perm_subject_domain: tuple = Depends(get_subject_domain),
    db_session=Depends(database.get_session),
) -> Optional[PlaysetResponse]:
    try:
        db = Handle(db_session=db_session, perm_subject=perm_subject_domain[0], perm_domain=perm_subject_domain[1])
        result = await db.get_playset_by_name(classroom_id, name)
        if result is None:
            raise HTTPException(status_code=404, detail="not_found")

        return result
    except PermissionException as e:
        logging.error(e)
        raise HTTPException(status_code=401, detail="not_allowed") from e


@router.get(
    "/videos/classrooms/{classroom_id}/playsets_by_date/{date}",
    dependencies=[Depends(verify_token), Depends(can_read)],
    response_model=PlaysetListResponse,
)
async def load_playsets_by_date(
    classroom_id: str,
    date: str,
    perm_subject_domain: tuple = Depends(get_subject_domain),
    db_session=Depends(database.get_session),
) -> Optional[PlaysetListResponse]:
    try:
        db = Handle(db_session=db_session, perm_subject=perm_subject_domain[0], perm_domain=perm_subject_domain[1])
        result = await db.get_playsets_by_date(classroom_id, date)
        if result is None:
            raise HTTPException(status_code=404, detail="not_found")

        return result
    except PermissionException as e:
        logging.error(e)
        raise HTTPException(status_code=401, detail="not_allowed") from e


@router.post(
    "/videos/playsets",
    dependencies=[Depends(verify_token), Depends(can_write)],
    response_model=Optional[PlaysetResponse],
)
async def create_playset(
    playset: Playset, perm_subject_domain: tuple = Depends(get_subject_domain), db_session=Depends(database.get_session)
):
    try:
        db = Handle(db_session=db_session, perm_subject=perm_subject_domain[0], perm_domain=perm_subject_domain[1])

        classroom = await db.get_classroom(playset.classroom_id)
        if classroom is None:
            try:
                environment = honeycomb_client.get_environment_by_id(environment_id=str(playset.classroom_id))
            except Exception:
                err = f"Classroom/environment ID ('{playset.classroom_id}') not found"
                logging.error(err)
                return

            await db.create_classroom(Classroom(id=environment["environment_id"], name=environment["name"]))

        return await db.create_playset(playset)
    except PermissionException as e:
        logging.error(e)
        raise HTTPException(status_code=401, detail="not_allowed") from e


@router.delete(
    "/videos/playsets/{playset_id}", dependencies=[Depends(verify_token), Depends(can_delete)], response_model=None
)
async def delete_playset(
    playset_id: str, perm_subject_domain: tuple = Depends(get_subject_domain), db_session=Depends(database.get_session)
):
    try:
        db = Handle(db_session=db_session, perm_subject=perm_subject_domain[0], perm_domain=perm_subject_domain[1])
        if await db.delete_playset(playset_id):
            return

        raise HTTPException(status_code=404, detail="not_found")
    except PermissionException as e:
        logging.error(e)
        raise HTTPException(status_code=401, detail="not_allowed") from e


@router.post(
    "/videos/playsets/{playset_id}/videos",
    dependencies=[Depends(verify_token), Depends(can_write)],
    response_model=VideoResponse,
)
async def create_video(
    playset_id: str,
    video: Video,
    perm_subject_domain: tuple = Depends(get_subject_domain),
    db_session=Depends(database.get_session),
) -> VideoResponse:
    try:
        db = Handle(db_session=db_session, perm_subject=perm_subject_domain[0], perm_domain=perm_subject_domain[1])
        video.playset_id = playset_id
        return await db.create_video(video)
    except PermissionException as e:
        logging.error(e)
        raise HTTPException(status_code=401, detail="not_allowed") from e


@router.get("/videos/{classroom_id}/{playest_name}/{filename}", dependencies=[Depends(verify_token), Depends(can_read)])
async def videos_root(
    classroom_id: str, playest_name: str, filename: str, perm_subject_domain: tuple = Depends(get_subject_domain)
) -> FileResponse:
    resp = await check_requests(
        [AuthRequest(sub=perm_subject_domain[0], dom=perm_subject_domain[1], obj=f"{classroom_id}:videos", act="read")]
    )
    if not resp[0]["allow"]:
        raise HTTPException(status_code=401, detail="not_allowed")

    path = f"{STATIC_PATH}/{classroom_id}/{playest_name}/{filename}"
    return FileResponse(Path(path).resolve())


@router.get(
    "/videos/{classroom_id}/{playest_name}/{camera_name}/{filename}",
    dependencies=[Depends(verify_token), Depends(can_read)],
)
async def videos(
    classroom_id: str,
    playest_name: str,
    camera_name: str,
    filename: str,
    perm_subject_domain: tuple = Depends(get_subject_domain),
) -> FileResponse:
    resp = await check_requests(
        [AuthRequest(sub=perm_subject_domain[0], dom=perm_subject_domain[1], obj=f"{classroom_id}:videos", act="read")]
    )
    if not resp[0]["allow"]:
        raise HTTPException(status_code=401, detail="not_allowed")

    path = f"{STATIC_PATH}/{classroom_id}/{playest_name}/{camera_name}/{filename}"
    return FileResponse(Path(path).resolve())
