import logging
import time
import traceback

from nio import RoomMessageText, MatrixRoom, MegolmEvent, InviteMemberEvent, JoinError

from matrix_gpt import MatrixClientHelper
from matrix_gpt.api_client_manager import api_client_helper
from matrix_gpt.chat_functions import is_this_our_thread, get_thread_content, check_command_prefix, check_authorized
from matrix_gpt.config import global_config
from matrix_gpt.generate import generate_ai_response
from matrix_gpt.generate_clients.command_info import CommandInfo

logger = logging.getLogger('MatrixGPT').getChild('HandleActions')


async def do_reply_msg(client_helper: MatrixClientHelper, room: MatrixRoom, requestor_event: RoomMessageText, command_info: CommandInfo, command_activated: bool):
    try:
        raw_msg = requestor_event.body.strip().strip('\n')
        msg = raw_msg if not command_activated else raw_msg[len(command_info.trigger):].strip()  # Remove the command prefix
        await generate_ai_response(
            client_helper=client_helper,
            room=room,
            event=requestor_event,
            msg=msg,
            command_info=command_info,
        )
    except Exception:
        logger.critical(traceback.format_exc())
        await client_helper.react_to_event(room.room_id, requestor_event.event_id, '❌')
        raise


async def do_reply_threaded_msg(client_helper: MatrixClientHelper, room: MatrixRoom, requestor_event: RoomMessageText):
    client = client_helper.client

    is_our_thread, sent_command_prefix, command_info = await is_this_our_thread(client, room, requestor_event)
    if not is_our_thread:  # or room.member_count == 2
        return

    if not check_authorized(requestor_event.sender, command_info.allowed_to_chat):
        await client_helper.react_to_event(room.room_id, requestor_event.event_id, '🚫', extra_error='Not allowed to chat.' if global_config['send_extra_messages'] else None)
        return
    if not check_authorized(requestor_event.sender, command_info.allowed_to_thread):
        await client_helper.react_to_event(room.room_id, requestor_event.event_id, '🚫', extra_error='Not allowed to thread.' if global_config['send_extra_messages'] else None)
        return

    try:
        # TODO: sync this with redis so that we don't clear the typing state if another response is also processing
        await client.room_typing(room.room_id, typing_state=True, timeout=30000)

        thread_content = await get_thread_content(client, room, requestor_event)
        api_client = api_client_helper.get_client(command_info.api_type, client_helper)
        for event in thread_content:
            if isinstance(event, MegolmEvent):
                await client_helper.send_text_to_room(
                    room.room_id,
                    '❌ 🔐 Decryption Failure',
                    reply_to_event_id=event.event_id,
                    thread=True,
                    thread_root_id=thread_content[0].event_id
                )
                logger.critical(f'Decryption failure for event {event.event_id} in room {room.room_id}')
                await client.room_typing(room.room_id, typing_state=False, timeout=1000)
                return
            else:
                role = api_client.BOT_NAME if event.sender == client.user_id else api_client.HUMAN_NAME
                if isinstance(event, RoomMessageText):
                    thread_msg = event.body.strip().strip('\n')
                    api_client.append_msg(
                        role=role,
                        content=thread_msg if not check_command_prefix(thread_msg)[0] else thread_msg[len(sent_command_prefix):].strip(),
                    )
                elif command_info.vision:
                    await api_client.append_img(event, role)

        await generate_ai_response(
            client_helper=client_helper,
            room=room,
            event=requestor_event,
            msg=api_client.context,
            command_info=command_info,
            thread_root_id=thread_content[0].event_id
        )
    except:
        logger.error(traceback.format_exc())
        await client_helper.react_to_event(room.room_id, event.event_id, '❌')
        raise


async def do_join_channel(client_helper: MatrixClientHelper, room: MatrixRoom, event: InviteMemberEvent):
    if not check_authorized(event.sender, global_config['allowed_to_invite']) and room.room_id not in global_config['blacklist_rooms']:
        logger.info(f'Got invite to {room.room_id} from {event.sender} but rejected')
        return

    # Attempt to join 3 times before giving up.
    client = client_helper.client
    for attempt in range(3):
        result = await client.join(room.room_id)
        if isinstance(result, JoinError):
            logger.error(f'Error joining room {room.room_id} (attempt {attempt}): "{result.message}"')
            time.sleep(5)
        else:
            logger.info(f'Joined via invite: {room.room_id}')
            return
    else:
        logger.error(f'Unable to join room: {room.room_id}')


async def sound_off(room: MatrixRoom, event: RoomMessageText, client_helper: MatrixClientHelper):
    text_response = """## MatrixGPT

<https://git.evulid.cc/cyberes/MatrixGPT>

### Commands


`!matrixgpt`  -  show this help message.\n\n"""
    for command in global_config['command']:
        max_tokens = f' Max tokens: {command["max_tokens"]}.' if command['max_tokens'] > 0 else ''
        system_prompt_text = f" System prompt: yes." if command['system_prompt'] else ''
        injected_system_prompt_text = f" Injected system prompt: yes." if command['injected_system_prompt'] else ''
        help_text = f" ***{command['help'].strip('.')}.***" if command['help'] else ''
        vision_text = ' Vision: yes.' if command['vision'] else ''

        if command['model'] != 'copilot':
            text_response = text_response + f"`{command['trigger']}`  -  Model: {command['model']}. Temperature: {command['temperature']}.{max_tokens}{vision_text}{system_prompt_text}{injected_system_prompt_text}{help_text}\n\n"
        else:
            # Copilot is very basic.
            # TODO: make sure to update this if Copilot gets vision support.
            text_response = text_response + f"`{command['trigger']}`  -  Model: {command['model']}.{help_text}\n\n"
    return await client_helper.send_text_to_room(
        room.room_id,
        text_response,
        reply_to_event_id=event.event_id,
        markdown_convert=True
    )
