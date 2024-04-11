from typing import Tuple

from nio import RoomMessageImage, MatrixRoom, Event

from matrix_gpt import MatrixClientHelper
from matrix_gpt.generate_clients.command_info import CommandInfo


class ApiClient:
    _HUMAN_NAME = 'user'
    _BOT_NAME = 'assistant'

    def __init__(self, api_key: str, client_helper: MatrixClientHelper, room: MatrixRoom, event: Event):
        self._api_key = api_key
        self._client_helper = client_helper
        self._room = room
        self._event = event
        self._context = []

    def _create_client(self, base_url: str = None):
        raise NotImplementedError

    def check_ignore_request(self):
        return False

    def assemble_context(self, context: list, system_prompt: str = None, injected_system_prompt: str = None):
        assert not len(self._context)
        raise NotImplementedError

    def generate_text_msg(self, content: str, role: str):
        raise NotImplementedError

    def append_msg(self, content: str, role: str):
        raise NotImplementedError

    async def append_img(self, img_event: RoomMessageImage, role: str):
        raise NotImplementedError

    async def generate(self, command_info: CommandInfo, matrix_gpt_data: str = None) -> Tuple[str, dict | None]:
        raise NotImplementedError

    @property
    def context(self):
        return self._context.copy()

    @property
    def HUMAN_NAME(self):
        return self._HUMAN_NAME

    @property
    def BOT_NAME(self):
        return self._BOT_NAME
