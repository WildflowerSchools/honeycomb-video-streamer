import os

import honeycomb_io
import minimal_honeycomb


class HoneycombClient(object):
    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(
            self,
            url=os.getenv("HONEYCOMB_URI", "https://honeycomb.api.wildflower-tech.org/graphql"),
            auth_domain=os.getenv("HONEYCOMB_DOMAIN", os.getenv("AUTH0_DOMAIN", "wildflowerschools.auth0.com")),
            auth_client_id=os.getenv("HONEYCOMB_CLIENT_ID", os.getenv("AUTH0_CLIENT_ID", None)),
            auth_client_secret=os.getenv("HONEYCOMB_CLIENT_SECRET", os.getenv("AUTH0_CLIENT_SECRET", None)),
            auth_audience=os.getenv("HONEYCOMB_AUDIENCE", os.getenv("API_AUDIENCE", "wildflower-tech.org")),
    ):

        if auth_client_id is None:
            raise ValueError("HONEYCOMB_CLIENT_ID (or AUTH0_CLIENT_ID) is required")
        if auth_client_secret is None:
            raise ValueError("HONEYCOMB_CLIENT_SECRET (or AUTH0_CLIENT_SECRET) is required")

        token_uri = os.getenv("HONEYCOMB_TOKEN_URI", f"https://{auth_domain}/oauth/token")

        self.client: minimal_honeycomb.MinimalHoneycombClient = honeycomb_io.generate_client(
            uri=url,
            token_uri=token_uri,
            audience=auth_audience,
            client_id=auth_client_id,
            client_secret=auth_client_secret
        )

    def get_environment_by_name(self, environment_name):
        result = self.client.request(
            request_type="query",
            request_name='searchEnvironments',
            arguments={
                'query': {
                    'type': 'QueryExpression!',
                    'value': {
                        'operator': 'AND',
                        'children': [
                            {'operator': 'EQ', 'field': "name", 'value': environment_name},
                        ]
                    }
                }
            },
            return_object=[
                {
                    'data': [
                        'environment_id',
                        'name'
                    ]
                }
            ]
        )

        return result.get('data')[0]

    def get_environment_by_id(self, environment_id):
        result = self.client.request(
            request_type="query",
            request_name='searchEnvironments',
            arguments={
                'query': {
                    'type': 'QueryExpression!',
                    'value': {
                        'operator': 'AND',
                        'children': [
                            {'operator': 'EQ', 'field': "environment_id", 'value': environment_id},
                        ]
                    }
                }
            },
            return_object=[
                {
                    'data': [
                        'environment_id',
                        'name'
                    ]
                }
            ]
        )
        return result.get('data')[0]

    def get_assignments(self, environment_id):
        result = self.client.request(
            request_type="query",
            request_name='getEnvironment',
            arguments={'environment_id': environment_id},
            return_object=[
                'environment_id',
                'name',
                {
                    'assignments(current: true)': [
                        'assignment_id',
                        'assigned_type',
                        {
                            'assigned': [
                                {
                                    '... on Device': [
                                        'device_id',
                                        'device_type',
                                        'part_number',
                                        'name',
                                        'tag_id',
                                        'description',
                                        'serial_number',
                                        'mac_address'
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        )
        assignments = result.get("assignments")
        return [
            (assignment["assignment_id"], assignment["assigned"]["device_id"], assignment["assigned"]["name"])
            for assignment in assignments
            if assignment["assigned_type"] == "DEVICE"
               and assignment["assigned"]["device_type"] in ["PI3WITHCAMERA", "PI4WITHCAMERA"]
        ]
