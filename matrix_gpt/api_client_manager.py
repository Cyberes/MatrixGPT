import logging

from nio import MatrixRoom, Event

from matrix_gpt import MatrixClientHelper
from matrix_gpt.config import global_config
from matrix_gpt.generate_clients.anthropic import AnthropicApiClient
from matrix_gpt.generate_clients.copilot import CopilotClient
from matrix_gpt.generate_clients.openai import OpenAIClient

"""
Global variable to sync importing and sharing the configured module.
"""


class ApiClientManager:
    def __init__(self):
        self._openai_api_key = None
        self._openai_api_base = None
        self._anth_api_key = None
        self.logger = logging.getLogger('MatrixGPT').getChild('ApiClientManager')

    def _set_from_config(self):
        """
        Have to update the config because it may not be instantiated yet.
        """
        self._openai_api_key = global_config['openai'].get('api_key', 'MatrixGPT')
        self._anth_api_key = global_config['anthropic'].get('api_key')
        self._copilot_cookie = global_config['copilot'].get('api_key')

    def get_client(self, mode: str, client_helper: MatrixClientHelper, room: MatrixRoom, event: Event):
        if mode == 'openai':
            return self.openai_client(client_helper, room, event)
        elif mode == 'anthropic':
            return self.anth_client(client_helper, room, event)
        elif mode == 'copilot':
            return self.copilot_client(client_helper, room, event)
        else:
            raise Exception

    def openai_client(self, client_helper: MatrixClientHelper, room: MatrixRoom, event: Event):
        self._set_from_config()
        if not self._openai_api_key:
            self.logger.error('Missing an OpenAI API key!')
            return None
        return OpenAIClient(
            api_key=self._openai_api_key,
            client_helper=client_helper,
            room=room,
            event=event
        )

    def anth_client(self, client_helper: MatrixClientHelper, room: MatrixRoom, event: Event):
        self._set_from_config()
        if not self._anth_api_key:
            self.logger.error('Missing an Anthropic API key!')
            return None
        return AnthropicApiClient(
            api_key=self._anth_api_key,
            client_helper=client_helper,
            room=room,
            event=event
        )

    def copilot_client(self, client_helper, room: MatrixRoom, event: Event):
        self._set_from_config()
        if not self._copilot_cookie:
            self.logger.error('Missing a Copilot API key!')
            return None
        return CopilotClient(
            api_key=self._copilot_cookie,
            client_helper=client_helper,
            room=room,
            event=event
        )


api_client_helper = ApiClientManager()
