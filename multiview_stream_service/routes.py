import os

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import FileResponse

from wf_fastapi_auth0 import verify_token, get_profile
from .models import ClassroomList, ClassroomResponse, PlaysetResponse

from .database import get_allowed_classrooms, get_classroom, get_playset, classroom_allowed


router = APIRouter()

STATIC_PATH = os.environ.get("STATIC_PATH", "./public/videos")


async def can_access_classroom(request: Request, profile:str=Depends(get_profile)):
    classroom_id = request.path_params.get("classroom_id")
    if classroom_id:
        return classroom_allowed(classroom_id, profile.get("primaryEmail"))
    raise HTTPException(status_code=401, detail="missing_classroom_id")


@router.get("/videos", dependencies=[Depends(verify_token)], response_model=ClassroomList)
async def load_classroom_list(profile: dict = Depends(get_profile)):
    return get_allowed_classrooms(profile["primaryEmail"])


@router.get("/videos/{classroom_id}", dependencies=[Depends(verify_token), Depends(can_access_classroom)], response_model=ClassroomResponse)
async def load_classroom(classroom_id: str):
    return get_classroom(classroom_id)


@router.get("/videos/{classroom_id}/{playest_date}",
            dependencies=[Depends(verify_token), Depends(can_access_classroom)], response_model=PlaysetResponse)
async def load_playset(classroom_id: str, playest_date: str):
    return get_playset(classroom_id, playest_date)


@router.get("/videos/{classroom_id}/{playest_date}/{camera_name}/{filename}",
            dependencies=[Depends(verify_token), Depends(can_access_classroom)])
async def videos(classroom_id: str, playest_date: str, camera_name: str, filename: str):
    return FileResponse(f'{STATIC_PATH}/{classroom_id}/{playest_date}/{camera_name}/{filename}')
