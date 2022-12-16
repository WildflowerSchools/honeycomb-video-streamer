FROM python:3.9.13-slim

RUN apt update -y && apt install build-essential libpq-dev -y

RUN pip install poetry wheel --upgrade

RUN pip install uvicorn aiofiles 'wf-fastapi-auth0>=1.0.2' 'python-jose>=3.3.0' 'fastapi>=0.68' 'auth0-python>=3.16.2' 'cachetools>=4.2.2' 'sqlalchemy>=1.4.23' 'psycopg2>=2.9.1' 'pydantic[email]'

RUN mkdir -p /app

WORKDIR /app

COPY multiview_stream_service/ /app/multiview_stream_service/
COPY pyproject.toml setup.py /app/

#RUN poetry install --without dev
RUN poetry lock && poetry export -f requirements.txt --without dev | pip install -r /dev/stdin
CMD python -m multiview_stream_service
