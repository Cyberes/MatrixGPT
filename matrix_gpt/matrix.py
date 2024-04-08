import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Union, Optional

from markdown import markdown
from nio import AsyncClient, AsyncClientConfig, LoginError, Response, ErrorResponse, RoomSendResponse, SendRetryError, SyncError
from nio.responses import LoginResponse, SyncResponse


class MatrixClientHelper:
    """
    A simple wrapper class for common matrix-nio actions.
    """

    # Encryption is disabled because it's handled by Pantalaimon.
    client_config = AsyncClientConfig(max_limit_exceeded=0, max_timeouts=0, store_sync_tokens=True, encryption_enabled=False)

    def __init__(self, user_id: str, passwd: str, homeserver: str, store_path: str, device_id: str):
        self.user_id = user_id
        self.passwd = passwd

        self.homeserver = homeserver
        if not (self.homeserver.startswith("https://") or self.homeserver.startswith("http://")):
            self.homeserver = "https://" + self.homeserver

        self.store_path = Path(store_path).absolute().expanduser().resolve()
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.auth_file = self.store_path / (device_id.lower() + '.json')

        self.device_name = device_id
        self.client: AsyncClient = AsyncClient(homeserver=self.homeserver, user=self.user_id, config=self.client_config, device_id=device_id)
        self.logger = logging.getLogger('MatrixGPT').getChild('MatrixClientHelper')

    async def login(self) -> tuple[bool, LoginResponse | LoginError | None]:
        try:
            # If there are no previously-saved credentials, we'll use the password.
            if not os.path.exists(self.auth_file):
                self.logger.info('Using username/password')
                resp = await self.client.login(self.passwd, device_name=self.device_name)
                if isinstance(resp, LoginResponse):
                    self._write_details_to_disk(resp)
                    return True, resp
                else:
                    return False, resp
            else:
                # Otherwise the config file exists, so we'll use the stored credentials.
                self.logger.info('Using cached credentials')

                auth_details = self._read_details_from_disk()['auth']
                client = AsyncClient(auth_details["homeserver"])
                client.access_token = auth_details["access_token"]
                client.user_id = auth_details["user_id"]
                client.device_id = auth_details["device_id"]

                resp = await self.client.login(self.passwd, device_name=self.device_name)
                if isinstance(resp, LoginResponse):
                    self._write_details_to_disk(resp)
                    return True, resp
                else:
                    return False, resp
        except Exception:
            raise

    async def sync(self) -> SyncResponse | SyncError:
        last_sync = self._read_details_from_disk().get('extra', {}).get('last_sync')
        response = await self.client.sync(timeout=10000, full_state=True, since=last_sync)
        if isinstance(response, SyncError):
            raise Exception(response)
        self._write_details_to_disk(extra_data={'last_sync': response.next_batch})
        return response

    def run_sync_in_bg(self):
        """
        Run a sync in the background to update the `last_sync` value every 3 minutes.
        """
        asyncio.create_task(self._do_run_sync_in_bg())

    async def _do_run_sync_in_bg(self):
        while True:
            await self.sync()
            await asyncio.sleep(180)  # 3 minutes

    def _read_details_from_disk(self):
        if not self.auth_file.exists():
            return {}
        with open(self.auth_file, "r") as f:
            return json.load(f)

    def _write_details_to_disk(self, resp: LoginResponse = None, extra_data: dict = None) -> None:
        data = self._read_details_from_disk()
        if resp:
            data['auth'] = {
                'homeserver': self.homeserver,
                'user_id': resp.user_id,
                'device_id': resp.device_id,
                'access_token': resp.access_token,
            }
        if extra_data:
            data['extra'] = extra_data
        with open(self.auth_file, 'w') as f:
            json.dump(data, f, indent=4)

    async def react_to_event(self, room_id: str, event_id: str, reaction_text: str, extra_error: str = False, extra_msg: str = False) -> Union[Response, ErrorResponse]:
        content = {
            "m.relates_to": {
                "rel_type": "m.annotation",
                "event_id": event_id,
                "key": reaction_text
            },
            "m.matrixbot": {}
        }
        if extra_error:
            content["m.matrixbot"]["error"] = str(extra_error)
        if extra_msg:
            content["m.matrixbot"]["msg"] = str(extra_msg)
        return await self.client.room_send(room_id, "m.reaction", content, ignore_unverified_devices=True)

    async def send_text_to_room(self, room_id: str, message: str, notice: bool = False,
                                markdown_convert: bool = False, reply_to_event_id: Optional[str] = None,
                                thread: bool = False, thread_root_id: Optional[str] = None, extra_error: Optional[str] = None,
                                extra_msg: Optional[str] = None) -> Union[RoomSendResponse, ErrorResponse]:
        """Send text to a matrix room.

        Args:
            room_id: The ID of the room to send the message to.
            message: The message content.
            notice: Whether the message should be sent with an "m.notice" message type
                (will not ping users).
            markdown_convert: Whether to convert the message content to markdown.
                Defaults to true.
            reply_to_event_id: Whether this message is a reply to another event. The event
                ID this is message is a reply to.
            thread:
            thread_root_id:
            extra_msg:
            extra_error:

        Returns:
            A RoomSendResponse if the request was successful, else an ErrorResponse.

        """
        msgtype = "m.notice" if notice else "m.text"
        content = {"msgtype": msgtype, "format": "org.matrix.custom.html", "body": message}

        if markdown_convert:
            content["formatted_body"] = markdown(message, extensions=['fenced_code'])

        if reply_to_event_id:
            if thread:
                content["m.relates_to"] = {
                    'event_id': thread_root_id,
                    'is_falling_back': True,
                    "m.in_reply_to": {
                        "event_id": reply_to_event_id
                    },
                    'rel_type': "m.thread"
                }
            else:
                content["m.relates_to"] = {
                    "m.in_reply_to": {
                        "event_id": reply_to_event_id
                    }
                }

            # TODO: don't force this to string. what if we want to send an array?
            content["m.matrixgpt"] = {
                "error": str(extra_error),
                "msg": str(extra_msg),
            }
        try:
            return await self.client.room_send(room_id, "m.room.message", content, ignore_unverified_devices=True)
        except SendRetryError:
            self.logger.exception(f"Unable to send message response to {room_id}")
