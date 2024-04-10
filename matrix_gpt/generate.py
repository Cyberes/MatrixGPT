import asyncio
import logging
import traceback
from typing import Union

from nio import RoomSendResponse, MatrixRoom, RoomMessageText

from matrix_gpt import MatrixClientHelper
from matrix_gpt.api_client_manager import api_client_helper
from matrix_gpt.config import global_config
from matrix_gpt.generate_clients.command_info import CommandInfo

logger = logging.getLogger('MatrixGPT').getChild('Generate')


# TODO: process_chat() will set typing as false after generating.
# TODO: If there is still another query in-progress that typing state will be overwritten by the one that just finished.


async def generate_ai_response(
        client_helper: MatrixClientHelper,
        room: MatrixRoom,
        event: RoomMessageText,
        msg: Union[str, list],
        command_info: CommandInfo,
        thread_root_id: str = None,
):
    assert isinstance(command_info, CommandInfo)
    client = client_helper.client
    try:
        await client.room_typing(room.room_id, typing_state=True, timeout=global_config['response_timeout'] * 1000)

        api_client = api_client_helper.get_client(command_info.api_type, client_helper)
        messages = api_client.assemble_context(msg, system_prompt=command_info.system_prompt, injected_system_prompt=command_info.injected_system_prompt)

        if api_client.check_ignore_request():
            logger.debug(f'Reply to {event.event_id} was ignored by the model "{command_info.model}".')
            await client.room_typing(room.room_id, typing_state=False, timeout=1000)
            return

        response = None
        try:
            task = asyncio.create_task(api_client.generate(command_info))
            for task in asyncio.as_completed([task], timeout=global_config['response_timeout']):
                # TODO: add a while loop and heartbeat the background thread
                try:
                    response = await task
                    break
                except asyncio.TimeoutError:
                    logger.warning(f'Response to event {event.event_id} timed out.')
                    await client_helper.react_to_event(
                        room.room_id,
                        event.event_id,
                        '🕒',
                        extra_error='Request timed out.' if global_config['send_extra_messages'] else None
                    )
                    await client.room_typing(room.room_id, typing_state=False, timeout=1000)
                    return
        except Exception:
            logger.error(f'Exception when generating for event {event.event_id}: {traceback.format_exc()}')
            await client_helper.react_to_event(
                room.room_id,
                event.event_id,
                '❌',
                extra_error='Exception' if global_config['send_extra_messages'] else None
            )
            await client.room_typing(room.room_id, typing_state=False, timeout=1000)
            return

        if not response:
            logger.warning(f'Response to event {event.event_id} in room {room.room_id} was null.')
            await client_helper.react_to_event(
                room.room_id,
                event.event_id,
                '❌',
                extra_error='Response was null.' if global_config['send_extra_messages'] else None
            )
            await client.room_typing(room.room_id, typing_state=False, timeout=1000)
            return

        # The AI's response.
        text_response = response.strip().strip('\n')

        # Logging
        if global_config['logging']['log_full_response']:
            data = {'event_id': event.event_id, 'room': room.room_id, 'messages': messages, 'response': response}
            # Remove images from the logged data.
            for i in range(len(data['messages'])):
                if isinstance(data['messages'][i]['content'], list):
                    # Images are always sent as lists
                    if data['messages'][i]['content'][0].get('source', {}).get('media_type'):
                        # Anthropic
                        data['messages'][i]['content'][0]['source']['data'] = '...'
                    elif data['messages'][i]['content'][0].get('image_url'):
                        # OpenAI
                        data['messages'][i]['content'][0]['image_url']['url'] = '...'
            logger.debug(data)
        z = text_response.replace("\n", "\\n")
        logger.info(f'Reply to {event.event_id} --> {command_info.model} responded with "{z}"')

        # Send message to room
        resp = await client_helper.send_text_to_room(
            room.room_id,
            text_response,
            reply_to_event_id=event.event_id,
            thread=True,
            thread_root_id=thread_root_id if thread_root_id else event.event_id,
            markdown_convert=True
        )
        await client.room_typing(room.room_id, typing_state=False, timeout=1000)
        if not isinstance(resp, RoomSendResponse):
            logger.critical(f'Failed to respond to event {event.event_id} in room {room.room_id}:\n{vars(resp)}')
            await client_helper.react_to_event(room.room_id, event.event_id, '❌', extra_error='Exception' if global_config['send_extra_messages'] else None)
    except Exception:
        await client_helper.react_to_event(room.room_id, event.event_id, '❌', extra_error='Exception' if global_config['send_extra_messages'] else None)
        raise
