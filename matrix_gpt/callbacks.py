import asyncio
import logging
import time

from nio import (AsyncClient, InviteMemberEvent, MatrixRoom, MegolmEvent, RoomMessageText, UnknownEvent)

from .chat_functions import check_authorized, is_thread, check_command_prefix
from .config import global_config
from .handle_actions import do_reply_msg, do_reply_threaded_msg, do_join_channel, sound_off
from .matrix_helper import MatrixClientHelper


class MatrixBotCallbacks:
    def __init__(self, client: MatrixClientHelper):
        self.client_helper = client
        self.client: AsyncClient = client.client
        self.logger = logging.getLogger('MatrixGPT').getChild('MatrixBotCallbacks')
        self.startup_ts = time.time() * 1000
        self.seen_messages = set()

    async def handle_message(self, room: MatrixRoom, requestor_event: RoomMessageText) -> None:
        """
        Callback for when a message event is received.
        """
        mark_read_task = asyncio.create_task(self.client.room_read_markers(room.room_id, requestor_event.event_id, requestor_event.event_id))  # Mark all messages as read.
        msg = requestor_event.body.strip().strip('\n')
        if msg == "** Unable to decrypt: The sender's device has not sent us the keys for this message. **":
            self.logger.debug(f'Unable to decrypt event "{requestor_event.event_id} in room {room.room_id}')
            return
        if requestor_event.server_timestamp < self.startup_ts:
            return
        if requestor_event.sender == self.client.user_id:
            return
        if msg == '!bots' or msg == '!matrixgpt':
            self.logger.debug(f'Message from {requestor_event.sender} in {room.room_id} --> "{msg}"')
            await sound_off(room, requestor_event, self.client_helper)
            return
        if requestor_event.event_id in self.seen_messages:
            # Need to track messages manually because the sync background thread may trigger the callback.
            return
        self.seen_messages.add(requestor_event.event_id)
        command_activated, sent_command_prefix, command_info = check_command_prefix(msg)

        if not command_activated and is_thread(requestor_event):
            # Threaded messages
            self.logger.debug(f'Message from {requestor_event.sender} in {room.room_id} --> "{msg}"')
            # Start the task in the background and don't wait for it here or else we'll block everything.
            task = asyncio.create_task(do_reply_threaded_msg(self.client_helper, room, requestor_event))
        elif command_activated and not is_thread(requestor_event):
            # Everything else
            self.logger.debug(f'Message from {requestor_event.sender} in {room.room_id} --> "{msg}"')
            allowed_to_chat = command_info.allowed_to_chat + global_config['allowed_to_chat']
            if not check_authorized(requestor_event.sender, allowed_to_chat):
                await self.client_helper.react_to_event(room.room_id, requestor_event.event_id, '🚫', extra_error='Not allowed to chat.' if global_config['send_extra_messages'] else None)
                return
            task = asyncio.create_task(do_reply_msg(self.client_helper, room, requestor_event, command_info, command_activated))

    async def handle_invite(self, room: MatrixRoom, event: InviteMemberEvent) -> None:
        """Callback for when an invite is received. Join the room specified in the invite.
        Args:
            room: The room that we are invited to.
            event: The invite event.
        """
        """
        Since the InviteMemberEvent is fired for every m.room.member state received
        in a sync response's `rooms.invite` section, we will receive some that are
        not actually our own invite event (such as the inviter's membership).
        This makes sure we only call `callbacks.invite` with our own invite events.
        """
        if event.state_key == self.client.user_id:
            task = asyncio.create_task(do_join_channel(self.client_helper, room, event))

    async def decryption_failure(self, room: MatrixRoom, event: MegolmEvent) -> None:
        """
        Callback for when an event fails to decrypt. Inform the user.
        """
        await self.client.room_read_markers(room.room_id, event.event_id, event.event_id)
        if event.server_timestamp > self.startup_ts:
            self.logger.critical(f'Decryption failure for event {event.event_id} in room {room.room_id}')
            await self.client_helper.react_to_event(room.room_id, event.event_id, "❌ 🔐")

    async def unknown(self, room: MatrixRoom, event: UnknownEvent) -> None:
        """
        Callback for when an event with a type that is unknown to matrix-nio is received.
        Currently this is used for reaction events, which are not yet part of a released
        matrix spec (and are thus unknown to nio).
        """
        await self.client.room_read_markers(room.room_id, event.event_id, event.event_id)
