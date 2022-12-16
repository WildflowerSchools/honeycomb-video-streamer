import os
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from wf_fastapi_auth0 import verify_token, get_subject_domain
from wf_fastapi_auth0.wf_permissions import Predicate, check_requests
from .models import ClassroomList, ClassroomResponse, PlaysetResponse

from .database import get_allowed_classrooms, get_classroom, get_playset


router = APIRouter()

STATIC_PATH = os.environ.get("STATIC_PATH", "./public/videos")


async def can_access_classroom(classroom_id: str):
    resp = check_requests([Predicate(obj=f"{classroom_id}:videos", act="read")])
    return resp[0]["allow"]


@router.get("/videos", dependencies=[Depends(verify_token)], response_model=ClassroomList)
async def load_classroom_list(subject: tuple = Depends(get_subject_domain)):
    return await get_allowed_classrooms(subject)


@router.get("/videos/{classroom_id}", dependencies=[Depends(verify_token)], response_model=ClassroomResponse)
async def load_classroom(classroom_id: str):
    return get_classroom(classroom_id)


@router.get(
    "/videos/{classroom_id}/{playest_date}", dependencies=[Depends(verify_token)], response_model=PlaysetResponse
)
async def load_playset(classroom_id: str, playest_date: str):
    return get_playset(classroom_id, playest_date)


@router.get("/videos/{classroom_id}/{playest_date}/{filename}", dependencies=[Depends(verify_token)])
async def videos_root(classroom_id: str, playest_date: str, filename: str):
    path = f"{STATIC_PATH}/{classroom_id}/{playest_date}/{filename}"
    return FileResponse(Path(path).resolve())


@router.get("/videos/{classroom_id}/{playest_date}/{camera_name}/{filename}", dependencies=[Depends(verify_token)])
async def videos(classroom_id: str, playest_date: str, camera_name: str, filename: str):
    path = f"{STATIC_PATH}/{classroom_id}/{playest_date}/{camera_name}/{filename}"
    return FileResponse(Path(path).resolve())
