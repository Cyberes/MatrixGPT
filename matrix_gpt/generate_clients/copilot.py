import re
from typing import Union
from urllib.parse import urlparse

from nio import RoomMessageImage
from sydney import SydneyClient

from matrix_gpt.generate_clients.api_client import ApiClient
from matrix_gpt.generate_clients.command_info import CommandInfo

"""
This was written with sydney.py==0.20.4 but requirements.txt has not locked in a version because Bing's API may change. 
"""

_REGEX_ATTR_RE_STR = r'^\[(\d*)]:\s(https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_+.~#?&/=]*)\s*(\"\")*'
_REGEX_ATTR_RE = re.compile(_REGEX_ATTR_RE_STR)
_REGEX_ATTR_LINK_RE_STR = [r'\[\^\d*\^]\[', r']']
_REGEX_ATTR_LINK_RE = re.compile(r'\d*'.join(_REGEX_ATTR_LINK_RE_STR))


class CopilotClient(ApiClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _create_client(self, api_base: str = None):
        return None

    def append_msg(self, content: str, role: str):
        assert role in [self._HUMAN_NAME, self._BOT_NAME]
        self._context.append({'role': role, 'content': content})

    async def append_img(self, img_event: RoomMessageImage, role: str):
        raise NotImplementedError

    def check_ignore_request(self):
        if len(self._context) > 1:
            return True
        return False

    def assemble_context(self, messages: Union[str, list], system_prompt: str = None, injected_system_prompt: str = None):
        if isinstance(messages, list):
            messages = messages
        else:
            messages = [{'role': self._HUMAN_NAME, 'content': messages}]
        self._context = messages
        return messages

    async def generate(self, command_info: CommandInfo):
        async with SydneyClient(bing_cookies=self._api_key) as sydney:
            response = dict(await sydney.ask(self._context[0]['content'], citations=True, raw=True))
            bot_response = response['item']['messages'][-1]

            text_card = {}
            for msg in bot_response['adaptiveCards'][0]['body']:
                if msg.get('type') == 'TextBlock':
                    text_card = msg
                    break
            response_text = text_card.get('text', '')

            # Parse the attribution links.
            attributions_strs = []
            for line in response_text.split('\n'):
                m = re.match(_REGEX_ATTR_RE, line)
                if m:
                    i = int(m.group(1))
                    attributions_strs.insert(i, m.group(2))

        if len(attributions_strs):
            # Remove the original attributions from the text.
            response_text = response_text.split("\n", len(attributions_strs) + 1)[len(attributions_strs) + 1]

            # Add a list of attributions at the bottom of the response.
            response_text += '\n\nCitations:'
            for i in range(len(attributions_strs)):
                url = attributions_strs[i]
                domain = urlparse(url).netloc
                response_text += f'\n\n{i + 1}. [{domain}]({url})'

            # Add links to the inline attributions.
            for match in re.findall(_REGEX_ATTR_LINK_RE, response_text):
                match_clean = re.sub(r'\[\^\d*\^]', '', match)
                i = int(re.match(r'\[(\d*)]', match_clean).group(1))
                assert i - 1 >= 0
                new_str = f'[[{i}]]({attributions_strs[i - 1]})'
                n = response_text.replace(match, new_str)
                response_text = n

        response_text += "\n\n*Copilot lacks a context mechanism so the bot cannot respond past the first message. Conversations with Copilot are not private.*"
        return response_text
