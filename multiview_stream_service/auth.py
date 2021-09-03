import os

from auth0.v3.management.users import Users
from auth0.v3.authentication import GetToken
# from fastapi_auth0 import Auth0
from fastapi import Depends, HTTPException, Request
from fastapi.security.http import HTTPBearer

from cachetools.func import ttl_cache
from jose import jwt
import requests

from .database import classroom_allowed


AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN")
API_AUDIENCE = os.environ.get("API_AUDIENCE")
ALGORITHMS = ["RS256"]
CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID")
CLIENT_SECRET = os.environ.get("AUTH0_CLIENT_SECRET")


class AuthError(HTTPException):
    pass

@ttl_cache(ttl=60 * 60 * 4)
def admin_token():
    get_token = GetToken(AUTH0_DOMAIN)
    token = get_token.client_credentials(CLIENT_ID, CLIENT_SECRET, f'https://{AUTH0_DOMAIN}/api/v2/')
    api_token = token['access_token']
    return api_token


async def verify_token(authorization = Depends(HTTPBearer())):
    token = authorization.credentials
    unverified_header = jwt.get_unverified_header(token)
    rsa_key = load_rsa_key(unverified_header["kid"])
    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=ALGORITHMS,
            audience=API_AUDIENCE,
            issuer="https://" + AUTH0_DOMAIN + "/"
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="token_expired") from e
    except jwt.JWTClaimsError as e:
        raise HTTPException(status_code=401, detail="invalid_claims") from e
    except Exception as e:
        raise HTTPException(status_code=401, detail="invalid_header") from e


async def get_profile(authorization: str = Depends(HTTPBearer())):
    authentication = await verify_token(authorization)
    if "gty" not in authentication:
        user_id = authentication["sub"]
        u = Users(AUTH0_DOMAIN, admin_token())
        return u.get(user_id)  # , ["email", "app_metadata"])
    # gty = authentication["gty"]
    # should figure out how to determine which token it is and how to validate access.
    raise HTTPException(status_code=401, detail="user_token_required")


async def can_access_classroom(request: Request, profile:str=Depends(get_profile)):
    classroom_id = request.path_params.get("classroom_id")
    if classroom_id:
        return classroom_allowed(classroom_id, profile.get("primaryEmail"))
    raise HTTPException(status_code=401, detail="missing_classroom_id")


@ttl_cache(ttl=60 * 60)
def load_certs():
    return requests.get("https://wildflowerschools.auth0.com/.well-known/jwks.json").json()


@ttl_cache(ttl=60 * 60)
def load_rsa_key(kid):
    rsa_key = None
    jwks = load_certs()
    for key in jwks["keys"]:
        if key["kid"] == kid:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
    return rsa_key
