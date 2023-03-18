import logging
from typing import List, Optional, Union

from markdown import markdown
from nio import (
    AsyncClient,
    ErrorResponse,
    Event, MatrixRoom,
    MegolmEvent,
    Response,
    RoomMessageText, RoomSendResponse,
    SendRetryError,
)

logger = logging.getLogger('MatrixGPT')


async def send_text_to_room(
        client: AsyncClient,
        room_id: str,
        message: str,
        notice: bool = False,
        markdown_convert: bool = True,
        reply_to_event_id: Optional[str] = None,
        thread: bool = False,
        thread_root_id: str = None
) -> Union[RoomSendResponse, ErrorResponse]:
    """Send text to a matrix room.

    Args:
        client: The client to communicate to matrix with.

        room_id: The ID of the room to send the message to.

        message: The message content.

        notice: Whether the message should be sent with an "m.notice" message type
            (will not ping users).

        markdown_convert: Whether to convert the message content to markdown.
            Defaults to true.

        reply_to_event_id: Whether this message is a reply to another event. The event
            ID this is message is a reply to.

    Returns:
        A RoomSendResponse if the request was successful, else an ErrorResponse.
    """
    # Determine whether to ping room members or not
    msgtype = "m.notice" if notice else "m.text"

    content = {
        "msgtype": msgtype,
        "format": "org.matrix.custom.html",
        "body": message,
    }

    if markdown_convert:
        content["formatted_body"] = markdown(message)

    if reply_to_event_id:
        if thread:
            content["m.relates_to"] = {
                'event_id': thread_root_id,
                'is_falling_back': True,
                "m.in_reply_to": {
                    "event_id": reply_to_event_id
                },
                'rel_type': "m.thread"
            }
        else:
            content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to_event_id}}

    try:
        return await client.room_send(
            room_id,
            "m.room.message",
            content,
            ignore_unverified_devices=True,
        )
    except SendRetryError:
        logger.exception(f"Unable to send message response to {room_id}")


def make_pill(user_id: str, displayname: str = None) -> str:
    """Convert a user ID (and optionally a display name) to a formatted user 'pill'

    Args:
        user_id: The MXID of the user.

        displayname: An optional displayname. Clients like Element will figure out the
            correct display name no matter what, but other clients may not. If not
            provided, the MXID will be used instead.

    Returns:
        The formatted user pill.
    """
    if not displayname:
        # Use the user ID as the displayname if not provided
        displayname = user_id

    return f'<a href="https://matrix.to/#/{user_id}">{displayname}</a>'


async def react_to_event(
        client: AsyncClient,
        room_id: str,
        event_id: str,
        reaction_text: str,
) -> Union[Response, ErrorResponse]:
    """Reacts to a given event in a room with the given reaction text

    Args:
        client: The client to communicate to matrix with.

        room_id: The ID of the room to send the message to.

        event_id: The ID of the event to react to.

        reaction_text: The string to react with. Can also be (one or more) emoji characters.

    Returns:
        A nio.Response or nio.ErrorResponse if an error occurred.

    Raises:
        SendRetryError: If the reaction was unable to be sent.
    """
    content = {
        "m.relates_to": {
            "rel_type": "m.annotation",
            "event_id": event_id,
            "key": reaction_text,
        }
    }

    return await client.room_send(
        room_id,
        "m.reaction",
        content,
        ignore_unverified_devices=True,
    )


async def decryption_failure(self, room: MatrixRoom, event: MegolmEvent) -> None:
    """Callback for when an event fails to decrypt. Inform the user"""
    # logger.error(
    #     f"Failed to decrypt event '{event.event_id}' in room '{room.room_id}'!"
    #     f"\n\n"
    #     f"Tip: try using a different device ID in your config file and restart."
    #     f"\n\n"
    #     f"If all else fails, delete your store directory and let the bot recreate "
    #     f"it (your reminders will NOT be deleted, but the bot may respond to existing "
    #     f"commands a second time)."
    # )

    user_msg = (
        "Unable to decrypt this message. "
        "Check whether you've chosen to only encrypt to trusted devices."
    )

    await send_text_to_room(
        self.client,
        room.room_id,
        user_msg,
        reply_to_event_id=event.event_id,
    )


def is_thread(event: RoomMessageText):
    return event.source['content'].get('m.relates_to', {}).get('rel_type') == 'm.thread'


async def get_thread_content(client: AsyncClient, room: MatrixRoom, base_event: RoomMessageText) -> List[Event]:
    messages = []
    new_event = (await client.room_get_event(room.room_id, base_event.event_id)).event
    while True:
        if new_event.source['content'].get('m.relates_to', {}).get('rel_type') == 'm.thread':
            messages.append(new_event)
        else:
            break
        new_event = (await client.room_get_event(room.room_id, new_event.source['content']['m.relates_to']['m.in_reply_to']['event_id'])).event
    messages.append((await client.room_get_event(room.room_id, base_event.source['content']['m.relates_to']['event_id'])).event)  # put the root event in the array
    messages.reverse()
    return messages


async def process_chat(client, room, event, command, store, openai, thread_root_id: str = None):
    if not store.check_seen_event(event.event_id):
        await client.room_typing(room.room_id, typing_state=True, timeout=3000)
        # if self.reply_in_thread:
        #     thread_content = await get_thread_content(self.client, self.room, self.event)

        if isinstance(command, list):
            messages = command
        else:
            messages = [
                {'role': 'user', 'content': command},
            ]

        response = openai['openai'].ChatCompletion.create(
            model=openai['model'],
            messages=messages,
            temperature=0,
        )
        logger.debug(response)
        text_response = response["choices"][0]["message"]["content"].strip().strip('\n')
        logger.info(f'Reply to {event.event_id} --> "{command}" and bot responded with "{text_response}"')
        resp = await send_text_to_room(client, room.room_id, text_response, reply_to_event_id=event.event_id, thread=True, thread_root_id=thread_root_id if thread_root_id else event.event_id)
        await client.room_typing(room.room_id, typing_state=False, timeout=3000)
        store.add_event_id(event.event_id)
        store.add_event_id(resp.event_id)
    # else:
    #     logger.info(f'Not responding to seen event {event.event_id}')


def check_authorized(string, to_check):
    def check_str(s, c):
        if c != 'all':
            if '@' not in c and ':' not in c:
                # Homeserver
                if s.split(':')[-1] in c:
                    return True
            elif s in c:
                # By username
                return True
        elif c == 'all':
            return True
        return False

    if isinstance(to_check, str):
        return check_str(string, to_check)
    elif isinstance(to_check, list):
        output = False
        for item in to_check:
            print(string, item, check_str(string, item))
            if check_str(string, item):
                output = True
        return output
    else:
        raise Exception
