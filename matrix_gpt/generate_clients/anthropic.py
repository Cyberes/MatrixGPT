from typing import Union

from anthropic import AsyncAnthropic

from matrix_gpt.generate_clients.api_client import ApiClient
from matrix_gpt.generate_clients.command_info import CommandInfo


class AnthropicApiClient(ApiClient):
    def __init__(self, api_key: str):
        super().__init__(api_key)

    def _create_client(self, base_url: str = None):
        return AsyncAnthropic(
            api_key=self.api_key
        )

    def assemble_context(self, messages: Union[str, list], system_prompt: str = None, injected_system_prompt: str = None):
        if isinstance(messages, list):
            messages = messages
        else:
            messages = [{"role": self._HUMAN_NAME, "content": [{"type": "text", "text": str(messages)}]}]
        self._context = messages
        return messages

    def append_msg(self, content: str, role: str):
        assert role in [self._HUMAN_NAME, self._BOT_NAME]
        self._context.append({"role": role, "content": [{"type": "text", "text": str(content)}]})

    async def generate(self, command_info: CommandInfo):
        r = await self._create_client().messages.create(
            model=command_info.model,
            max_tokens=None if command_info.max_tokens == 0 else command_info.max_tokens,
            temperature=command_info.temperature,
            system='' if not command_info.system_prompt else command_info.system_prompt,
            messages=self.context
        )
        return r.content[0].text
