import logging
from typing import List, Tuple
from urllib.parse import urlparse

from nio import AsyncClient, Event, MatrixRoom, RoomGetEventResponse, RoomMessageText

from matrix_gpt.config import global_config
from matrix_gpt.generate_clients.command_info import CommandInfo

logger = logging.getLogger('MatrixGPT').getChild('ChatFunctions')


def is_thread(event: RoomMessageText):
    return event.source['content'].get('m.relates_to', {}).get('rel_type') == 'm.thread'


def check_command_prefix(string: str) -> Tuple[bool, str | None, CommandInfo | None]:
    for k, v in global_config.command_prefixes.items():
        if string.startswith(f'{k} '):
            command_info = CommandInfo(**v)
            return True, k, command_info
    return False, None, None


async def is_this_our_thread(client: AsyncClient, room: MatrixRoom, event: RoomMessageText) -> Tuple[bool, str | None, CommandInfo | None]:
    base_event_id = event.source['content'].get('m.relates_to', {}).get('event_id')
    if base_event_id:
        e = await client.room_get_event(room.room_id, base_event_id)
        if not isinstance(e, RoomGetEventResponse):
            logger.critical(f'Failed to get event in is_this_our_thread(): {vars(e)}')
            return False, None, None
        else:
            return check_command_prefix(e.event.body)
    else:
        return False, None, None


async def get_thread_content(client: AsyncClient, room: MatrixRoom, base_event: RoomMessageText) -> List[Event]:
    messages = []

    # This is the event of the message that was just sent.
    new_event = (await client.room_get_event(room.room_id, base_event.event_id)).event

    while True:
        if new_event.source['content'].get('m.relates_to', {}).get('rel_type') == 'm.thread':
            # Put the event in the messages list only if it's related to the thread we're parsing.
            messages.append(new_event)
        else:
            break
        # Fetch the next event.
        new_event = (await client.room_get_event(
            room.room_id,
            new_event.source['content']['m.relates_to']['m.in_reply_to']['event_id'])
                     ).event

    # Put the root event in the array.
    messages.append((await client.room_get_event(
        room.room_id, base_event.source['content']['m.relates_to']['event_id'])
                     ).event)
    messages.reverse()
    return messages


def check_authorized(string, to_check):
    def check_str(s, c):
        if c == 'all':
            return True
        else:
            if '@' not in c and ':' not in c:
                # Homeserver
                if s.split(':')[-1] in c:
                    return True
            elif s in c:
                # By username
                return True
        return False

    if isinstance(to_check, str):
        return check_str(string, to_check)
    elif isinstance(to_check, list):
        output = False
        for item in to_check:
            if check_str(string, item):
                output = True
        return output
    else:
        raise Exception


async def download_mxc(url: str, client: AsyncClient) -> bytes:
    mxc = urlparse(url)
    response = await client.download(mxc.netloc, mxc.path.strip("/"))
    if hasattr(response, "body"):
        return response.body
    else:
        return b''
