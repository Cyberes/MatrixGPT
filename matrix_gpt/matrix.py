import json
import os
from pathlib import Path
from typing import Union

from nio import AsyncClient, AsyncClientConfig, LoginError
from nio import LoginResponse


class MatrixNioGPTHelper:
    """
    A simple wrapper class for common matrix-nio actions.
    """
    client = None

    client_config = AsyncClientConfig(max_limit_exceeded=0, max_timeouts=0, store_sync_tokens=True, encryption_enabled=True)

    def __init__(self, auth_file: Union[Path, str], user_id: str, passwd: str, homeserver: str, store_path: str, device_name: str = 'MatrixGPT', device_id: str = None):
        self.auth_file = auth_file
        self.user_id = user_id
        self.passwd = passwd

        self.homeserver = homeserver
        if not (self.homeserver.startswith("https://") or self.homeserver.startswith("http://")):
            self.homeserver = "https://" + self.homeserver

        self.store_path = store_path
        Path(self.store_path).mkdir(parents=True, exist_ok=True)

        self.device_name = device_name
        self.client = AsyncClient(self.homeserver, self.user_id, config=self.client_config, store_path=self.store_path, device_id=device_id)

    async def login(self) -> tuple[bool, LoginError] | tuple[bool, LoginResponse | None]:
        # If there are no previously-saved credentials, we'll use the password
        if not os.path.exists(self.auth_file):
            resp = await self.client.login(self.passwd, device_name=self.device_name)

            # check that we logged in succesfully
            if isinstance(resp, LoginResponse):
                self.write_details_to_disk(resp)
            else:
                # raise Exception(f'Failed to log in!\n{resp}')
                return False, resp
        else:
            # Otherwise the config file exists, so we'll use the stored credentials
            with open(self.auth_file, "r") as f:
                config = json.load(f)
                client = AsyncClient(config["homeserver"])
                client.access_token = config["access_token"]
                client.user_id = config["user_id"]
                client.device_id = config["device_id"]
            resp = await self.client.login(self.passwd, device_name=self.device_name)
        return True, resp

    def write_details_to_disk(self, resp: LoginResponse) -> None:
        """Writes the required login details to disk so we can log in later without
        using a password.

        Arguments:
            resp {LoginResponse} -- the successful client login response.
            homeserver -- URL of homeserver, e.g. "https://matrix.example.org"
        """
        with open(self.auth_file, "w") as f:
            json.dump({"homeserver": self.homeserver,  # e.g. "https://matrix.example.org"
                       "user_id": resp.user_id,  # e.g. "@user:example.org"
                       "device_id": resp.device_id,  # device ID, 10 uppercase letters
                       "access_token": resp.access_token,  # cryptogr. access token
                       }, f, )
