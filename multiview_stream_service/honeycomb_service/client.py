import os

import honeycomb


class HoneycombClient(object):
    __instance = None

    def __new__(cls, *args, **kwargs):
        print(cls.__instance)
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self,
                 url=os.getenv("HONEYCOMB_URI", "https://honeycomb.api.wildflower-tech.org/graphql"),
                 auth_domain=os.getenv("HONEYCOMB_DOMAIN", os.getenv("AUTH0_DOMAIN", "wildflowerschools.auth0.com")),
                 auth_client_id=os.getenv("HONEYCOMB_CLIENT_ID", os.getenv("AUTH0_CLIENT_ID", None)),
                 auth_client_secret=os.getenv("HONEYCOMB_CLIENT_SECRET", os.getenv("AUTH0_CLIENT_SECRET", None)),
                 auth_audience=os.getenv("HONEYCOMB_AUDIENCE", os.getenv("API_AUDIENCE", "wildflower-tech.org"))):

        if auth_client_id is None:
            raise ValueError("HONEYCOMB_CLIENT_ID (or AUTH0_CLIENT_ID) is required")
        if auth_client_secret is None:
            raise ValueError("HONEYCOMB_CLIENT_SECRET (or AUTH0_CLIENT_SECRET) is required")

        token_uri = os.getenv("HONEYCOMB_TOKEN_URI", f"https://{auth_domain}/oauth/token")

        self.client = honeycomb.HoneycombClient(
            uri=url,
            client_credentials={
                "token_uri": token_uri,
                "audience": auth_audience,
                "client_id": auth_client_id,
                "client_secret": auth_client_secret
            }
        )

    def get_environment_by_name(self, environment_name):
        environments = self.client.query.findEnvironment(name=environment_name)
        return environments.data[0]

    def get_environment_by_id(self, environment_id):
        environment = self.client.query.getEnvironment(environment_id=environment_id)
        return environment.to_json()
