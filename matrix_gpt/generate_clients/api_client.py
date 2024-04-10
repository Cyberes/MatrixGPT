from typing import Union

from nio import RoomMessageImage

from matrix_gpt import MatrixClientHelper
from matrix_gpt.generate_clients.command_info import CommandInfo


class ApiClient:
    _HUMAN_NAME = 'user'
    _BOT_NAME = 'assistant'

    def __init__(self, api_key: str, client_helper: MatrixClientHelper):
        self._api_key = api_key
        self._client_helper = client_helper
        self._context = []

    def _create_client(self, base_url: str = None):
        raise NotImplementedError

    def check_ignore_request(self):
        return False

    def assemble_context(self, messages: Union[str, list], system_prompt: str = None, injected_system_prompt: str = None):
        raise NotImplementedError

    def generate_text_msg(self, content: str, role: str):
        raise NotImplementedError

    def append_msg(self, content: str, role: str):
        raise NotImplementedError

    async def append_img(self, img_event: RoomMessageImage, role: str):
        raise NotImplementedError

    async def generate(self, command_info: CommandInfo):
        raise NotImplementedError

    @property
    def context(self):
        return self._context

    @property
    def HUMAN_NAME(self):
        return self._HUMAN_NAME

    @property
    def BOT_NAME(self):
        return self._BOT_NAME
