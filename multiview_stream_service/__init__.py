from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .routes import router

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://teacher-view.api.wildflower-tech.org",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StatusResponse(BaseModel):
    status: str = "OK"


@app.get("/", response_model=StatusResponse)
async def root():
    return StatusResponse()

app.include_router(router)