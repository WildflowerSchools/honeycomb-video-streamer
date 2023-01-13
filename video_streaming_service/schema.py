from sqlalchemy import MetaData, Column, Table, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID

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
