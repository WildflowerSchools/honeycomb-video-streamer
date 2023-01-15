from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import Database
from .routes import router

database = Database()
app = FastAPI()

origins = [
    "*",
    "http://127.0.0.1:3000",
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
