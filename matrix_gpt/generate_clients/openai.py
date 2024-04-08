from typing import Union

from openai import AsyncOpenAI

from matrix_gpt.config import global_config
from matrix_gpt.generate_clients.api_client import ApiClient
from matrix_gpt.generate_clients.command_info import CommandInfo


class OpenAIClient(ApiClient):
    def __init__(self, api_key: str):
        super().__init__(api_key)

    def _create_client(self, api_base: str = None):
        return AsyncOpenAI(
            api_key=self.api_key,
            base_url=api_base
        )

    def append_msg(self, content: str, role: str):
        assert role in [self._HUMAN_NAME, self._BOT_NAME]
        self._context.append({'role': role, 'content': content})

    def assemble_context(self, messages: Union[str, list], system_prompt: str = None, injected_system_prompt: str = None):
        if isinstance(messages, list):
            messages = messages
        else:
            messages = [{'role': self._HUMAN_NAME, 'content': messages}]

        if isinstance(system_prompt, str) and len(system_prompt):
            messages.insert(0, {"role": "system", "content": system_prompt})
        if (isinstance(injected_system_prompt, str) and len(injected_system_prompt)) and len(messages) >= 3:
            # Only inject the system prompt if this isn't the first reply.
            if messages[-1]['role'] == 'system':
                # Delete the last system message since we want to replace it with our inject prompt.
                del messages[-1]
            messages.insert(-1, {"role": "system", "content": injected_system_prompt})
        self._context = messages
        return messages

    async def generate(self, command_info: CommandInfo):
        r = await self._create_client(command_info.api_base).chat.completions.create(
            model=command_info.model,
            messages=self._context,
            temperature=command_info.temperature,
            timeout=global_config['response_timeout'],
            max_tokens=None if command_info.max_tokens == 0 else command_info.max_tokens
        )
        return r.choices[0].message.content
