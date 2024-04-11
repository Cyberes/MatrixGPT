import json
import re
import time
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from nio import RoomMessageImage
from sydney import SydneyClient
from sydney.exceptions import ThrottledRequestException

from matrix_gpt.config import global_config
from matrix_gpt.generate_clients.api_client import ApiClient
from matrix_gpt.generate_clients.command_info import CommandInfo

"""
This was written with sydney.py==0.20.4 but requirements.txt has not locked in a version because Bing's API may change.
"""

_REGEX_ATTR_RE_STR = r'^\[(\d*)]:\s(https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_+.~#?&/=]*)\s*(\"\")*'
_REGEX_ATTR_RE = re.compile(_REGEX_ATTR_RE_STR)
_REGEX_ATTR_LINK_RE_STR = [r'\[\^\d*\^]\[', r']']
_REGEX_ATTR_LINK_RE = re.compile(r'\d*'.join(_REGEX_ATTR_LINK_RE_STR))
_COPILOT_WARNING_STR = "\n\n*Conversations with Copilot are not private.*"


def encrypt_string(string: str) -> str:
    return Fernet(global_config['copilot']['event_encryption_key']).encrypt(string.encode()).decode('utf-8')


def decrypt_string(token: str) -> bytes:
    return Fernet(global_config['copilot']['event_encryption_key']).decrypt(token.encode())


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

    # def check_ignore_request(self):
    #     if len(self._context) > 1:
    #         return True
    #     return False

    def assemble_context(self, context: list, system_prompt: str = None, injected_system_prompt: str = None):
        assert not len(self._context)
        self._context = context
        for i in range(len(self._context)):
            if _COPILOT_WARNING_STR in self._context[i]['content']:
                self._context[i]['content'] = self._context[i]['content'].replace(_COPILOT_WARNING_STR, '', 1)

    async def generate(self, command_info: CommandInfo, matrix_gpt_data: str = None):
        # TODO: config option for style
        async with SydneyClient(bing_cookies=self._api_key, style='precise') as sydney:
            # Ignore any exceptions doing this since they will be caught by the caller.
            if matrix_gpt_data:
                decrypted_metadata = decrypt_string(matrix_gpt_data)
                conversation_metadata = json.loads(decrypted_metadata)
                sydney.conversation_signature = conversation_metadata["conversation_signature"]
                sydney.encrypted_conversation_signature = conversation_metadata["encrypted_conversation_signature"]
                sydney.conversation_id = conversation_metadata["conversation_id"]
                sydney.client_id = conversation_metadata["client_id"]
                sydney.invocation_id = conversation_metadata["invocation_id"]

            response = None
            for i in range(3):
                try:
                    response = dict(await sydney.ask(self._context[-1]['content'], citations=True, raw=True))
                    break
                except ThrottledRequestException:
                    time.sleep(10)
            if not response:
                # If this happens you should first try to change your cookies.
                # Otherwise, you've used all your credits for today.
                raise ThrottledRequestException

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
                    try:
                        assert i - 1 >= 0
                        new_str = f'[[{i}]]({attributions_strs[i - 1]})'
                    except:
                        raise Exception(f'Failed to parse attribution_str array.\n{attributions_strs}\n{i} {i - 1}\n{match_clean}{response_text}')
                    n = response_text.replace(match, new_str)
                    response_text = n

            event_data = json.dumps(
                {
                    "conversation_signature": sydney.conversation_signature,
                    "encrypted_conversation_signature": sydney.encrypted_conversation_signature,
                    "conversation_id": sydney.conversation_id,
                    "client_id": sydney.client_id,
                    "invocation_id": sydney.invocation_id,
                    "number_of_messages": sydney.number_of_messages,
                    "max_messages": sydney.max_messages,
                }
            )

        if len(self._context) == 1:
            response_text += _COPILOT_WARNING_STR

        # Store the conversation metadata in the response. It's encrypted for privacy purposes.
        custom_data = {
            'thread_root_event': self._event.event_id,
            'data': encrypt_string(event_data)
        }

        return response_text, custom_data
