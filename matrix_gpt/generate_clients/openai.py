from nio import RoomMessageImage
from openai import AsyncOpenAI

from matrix_gpt.chat_functions import download_mxc
from matrix_gpt.config import global_config
from matrix_gpt.generate_clients.api_client import ApiClient
from matrix_gpt.generate_clients.command_info import CommandInfo
from matrix_gpt.image import process_image


class OpenAIClient(ApiClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _create_client(self, api_base: str = None):
        return AsyncOpenAI(
            api_key=self._api_key,
            base_url=api_base
        )

    def append_msg(self, content: str, role: str):
        assert role in [self._HUMAN_NAME, self._BOT_NAME]
        self._context.append({'role': role, 'content': content})

    async def append_img(self, img_event: RoomMessageImage, role: str):
        """
        We crop the largest dimension of the image to 512px and then let the AI decide
        if it should use low or high res analysis.
        """
        assert role in [self._HUMAN_NAME, self._BOT_NAME]
        img_bytes = await download_mxc(img_event.url, self._client_helper.client)
        encoded_image = await process_image(img_bytes, resize_px=512)
        self._context.append({
            "role": role,
            'content': [{
                'type': 'image_url',
                'image_url': {
                    'url': f"data:image/png;base64,{encoded_image}",
                    'detail': 'auto'
                }
            }]
        })

    def assemble_context(self, context: list, system_prompt: str = None, injected_system_prompt: str = None):
        assert not len(self._context)
        self._context = context
        if isinstance(system_prompt, str) and len(system_prompt):
            self._context.insert(0, {"role": "system", "content": system_prompt})
        if (isinstance(injected_system_prompt, str) and len(injected_system_prompt)) and len(self._context) >= 3:
            # Only inject the system prompt if this isn't the first reply.
            if self._context[-1]['role'] == 'system':
                # Delete the last system message since we want to replace it with our inject prompt.
                del self._context[-1]
            self._context.insert(-1, {"role": "system", "content": injected_system_prompt})

    async def generate(self, command_info: CommandInfo, matrix_gpt_data: str = None):
        r = await self._create_client(command_info.api_base).chat.completions.create(
            model=command_info.model,
            messages=self._context,
            temperature=command_info.temperature,
            timeout=global_config['response_timeout'],
            max_tokens=None if command_info.max_tokens == 0 else command_info.max_tokens,
        )
        return r.choices[0].message.content, None
