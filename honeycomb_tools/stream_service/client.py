import os
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError
from typing import List, Optional
from urllib3 import Retry
from urllib.parse import urljoin
import uuid


from auth0.v3.authentication import GetToken

from ..log import logger

from . import models


class StreamServiceClient(object):
    def __init__(
        self,
        url=os.getenv("VIDEO_STREAM_SERVICE_URI", None),
        auth_domain: str = os.getenv("AUTH0_DOMAIN", "wildflowerschools.auth0.com"),
        auth_client_id: str = os.getenv("AUTH0_CLIENT_ID", None),
        auth_client_secret: str = os.getenv("AUTH0_CLIENT_SECRET", None),
        auth_audience: str = os.getenv(
            "VIDEO_STREAM_SERVICE_AUDIENCE", os.getenv("API_AUDIENCE", "wildflower-tech.org")
        ),
    ):
        self.url = url

        self.domain = auth_domain
        self.client_id = auth_client_id
        self.client_secret = auth_client_secret
        self.audience = auth_audience

        if self.url is None:
            raise ValueError("StreamServiceClient 'url' is not optional, set with VIDEO_STREAM_SERVICE_URI")
        if self.domain is None:
            raise ValueError("StreamServiceClient 'auth_domain' is not optional, set with AUTH0_DOMAIN")
        if self.client_id is None:
            raise ValueError("StreamServiceClient 'auth_client_id' is not optional, set with AUTH0_CLIENT_ID")
        if self.client_secret is None:
            raise ValueError("StreamServiceClient 'auth_client_secret' is not optional, set with AUTH0_CLIENT_SECRET")
        if self.audience is None:
            raise ValueError(
                "StreamServiceClient 'auth_audience' is not optional, set with VIDEO_STREAM_SERVICE_AUDIENCE"
            )

        self.session = self._request_session()

        self.access_token = None
        self.auth0_token_generator = GetToken(self.domain, timeout=10)

        self._reset_token()

    @staticmethod
    def _request_session():
        session = requests.Session()
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=4, backoff_factor=1.5, allowed_methods=None, status_forcelist=[429, 500, 502, 503, 504]
            )
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _reset_token(self):
        token = self.auth0_token_generator.client_credentials(
            client_id=self.client_id,
            client_secret=self.client_secret,
            audience=self.audience if self.audience is not None else f"https://{self.domain}/api/v2/",
        )

        self.access_token = token["access_token"]

    def _request(self, method="GET", path="/", params={}, body=None):
        headers = {"Authorization": f"Bearer {self.access_token}"}

        try:
            response = self.session.request(
                url=urljoin(self.url, path), method=method, headers=headers, params=params, data=body
            )
            response.raise_for_status()
            return response.json()
        except HTTPError as e:
            resp = e.response.json()
            if "error" in resp and resp["error"] == "expired_token":
                logger.warning("Token expired, attempting token refresh...")
                self._reset_token()
                logger.warning("Token refreshed")
            raise e
        except Exception as e:
            logger.error(e)
            raise e

    def _get(self, path="/", params={}):
        return self._request(path=path, params=params)

    def _post(self, path="/", params={}, body=None):
        return self._request(path=path, method="POST", params=params, body=body)

    def _delete(self, path="/", params={}, body=None):
        return self._request(path=path, method="DELETE", params=params, body=body)

    def get_playsets_by_date(self, environment_id, date) -> List[models.PlaysetResponse]:
        try:
            response = self._get(path=f"/videos/classrooms/{environment_id}/playsets_by_date/{date}")
            return models.PlaysetListResponse(**response).playsets
        except HTTPError as e:
            if e.response.status_code == 404:
                return []

    def get_playset_by_name(self, environment_id, playset_name) -> Optional[models.PlaysetResponse]:
        try:
            response = self._get(path=f"/videos/classrooms/{environment_id}/playset_by_name/{playset_name}")
            return models.PlaysetResponse(**response)
        except HTTPError as e:
            if e.response.status_code == 404:
                return None

    def delete_playset_by_name_if_exists(self, environment_id, playset_name):
        playset = self.get_playset_by_name(environment_id=environment_id, playset_name=playset_name)
        if playset is not None:
            self.delete_playset(playset_id=playset.id)

    def create_playset(self, playset: models.Playset) -> models.PlaysetResponse:
        response = self._post(path="/videos/playsets", body=playset.json())
        if response is None:
            raise ValueError("Failed creating playset, server responded with None")

        return models.PlaysetResponse(**response)

    def delete_playset(self, playset_id: uuid.UUID):
        return self._delete(
            path=f"/videos/playsets/{playset_id}",
        )

    def add_video_to_playset(self, video: models.Video) -> models.VideoResponse:
        response = self._post(path=f"/videos/playsets/{video.playset_id}/videos", body=video.json())
        return models.VideoResponse(**response)
