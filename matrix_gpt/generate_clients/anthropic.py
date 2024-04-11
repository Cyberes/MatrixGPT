from anthropic import AsyncAnthropic
from nio import RoomMessageImage

from matrix_gpt.chat_functions import download_mxc
from matrix_gpt.generate_clients.api_client import ApiClient
from matrix_gpt.generate_clients.command_info import CommandInfo
from matrix_gpt.image import process_image


class AnthropicApiClient(ApiClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _create_client(self, base_url: str = None):
        return AsyncAnthropic(
            api_key=self._api_key
        )

    def assemble_context(self, context: list, system_prompt: str = None, injected_system_prompt: str = None):
        assert not len(self._context)
        self._context = context
        self.verify_context()

    def verify_context(self):
        """
        Verify that the context alternates between the human and assistant, inserting the opposite user type if it does not alternate correctly.
        """
        i = 0
        while i < len(self._context) - 1:
            if self._context[i]['role'] == self._context[i + 1]['role']:
                dummy = self.generate_text_msg(f'<{self._BOT_NAME} did not respond>', self._BOT_NAME) if self._context[i]['role'] == self._HUMAN_NAME else self.generate_text_msg(f'<{self._HUMAN_NAME} did not respond>', self._HUMAN_NAME)
                self._context.insert(i + 1, dummy)
            i += 1
        # if self._context[-1]['role'] == self._HUMAN_NAME:
        #     self._context.append(self.generate_text_msg(f'<{self._BOT_NAME} did not respond>', self._BOT_NAME))

    def generate_text_msg(self, content: str, role: str):
        assert role in [self._HUMAN_NAME, self._BOT_NAME]
        return {"role": role, "content": [{"type": "text", "text": str(content)}]}

    def append_msg(self, content: str, role: str):
        assert role in [self._HUMAN_NAME, self._BOT_NAME]
        self._context.append(self.generate_text_msg(content, role))

    async def append_img(self, img_event: RoomMessageImage, role: str):
        assert role in [self._HUMAN_NAME, self._BOT_NAME]
        img_bytes = await download_mxc(img_event.url, self._client_helper.client)
        encoded_image = await process_image(img_bytes, resize_px=784)
        self._context.append({
            "role": role,
            'content': [{
                'type': 'image',
                'source': {
                    'type': 'base64',
                    'media_type': 'image/png',
                    'data': encoded_image
                }
            }]
        })

    async def generate(self, command_info: CommandInfo, matrix_gpt_data: str = None):
        r = await self._create_client().messages.create(
            model=command_info.model,
            max_tokens=None if command_info.max_tokens == 0 else command_info.max_tokens,
            temperature=command_info.temperature,
            system='' if not command_info.system_prompt else command_info.system_prompt,
            messages=self.context
        )
        return r.content[0].text, None
