FROM python:3.8

RUN apt install libpq-dev

RUN pip install wheel --upgrade

RUN pip install 'fastapi>=0.68' 'auth0-python>=3.16.2' 'cachetools>=4.2.2' 'sqlalchemy>=1.4.23' 'psycopg2>=2.9.1'

RUN mkdir -p /app

WORKDIR /app


COPY multiview_stream_service/ /app/multiview_stream_service/
COPY setup.py /app/setup.py

RUN pip install -e .

CMD uvicorn multiview_stream_service:app
