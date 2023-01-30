from asyncache import cached
from cachetools import TTLCache
from typing import List, Tuple

from wf_fastapi_auth0.wf_permissions import AuthRequest, check_requests


class CacheableAuthRequest(AuthRequest):
    def __hash__(self):
        return hash((type(self),) + tuple(self.__dict__.values()))


@cached(TTLCache(maxsize=128, ttl=60))
async def cached_check_requests(reqs: Tuple[CacheableAuthRequest]):
    return await check_requests(list(reqs))
