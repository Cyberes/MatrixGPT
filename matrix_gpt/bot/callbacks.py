# https://github.com/anoadragon453/nio-template
import logging
import time

from nio import (AsyncClient, InviteMemberEvent, JoinError, MatrixRoom, MegolmEvent, RoomMessageText, UnknownEvent, )

from .bot_commands import Command
from .chat_functions import check_authorized, get_thread_content, is_this_our_thread, is_thread, process_chat, react_to_event, send_text_to_room
# from .config import Config
from .storage import Storage

logger = logging.getLogger('MatrixGPT')


class Callbacks:
    def __init__(self, client: AsyncClient, store: Storage, command_prefix: str, openai, reply_in_thread, allowed_to_invite, allowed_to_chat='all', system_prompt: str = None, log_full_response: bool = False, injected_system_prompt: bool = False):
        """
        Args:
            client: nio client used to interact with matrix.

            store: Bot storage.

            config: Bot configuration parameters.
        """
        self.client = client
        self.store = store
        # self.config = config
        self.command_prefix = command_prefix
        self.openai = openai
        self.startup_ts = time.time_ns() // 1_000_000
        self.reply_in_thread = reply_in_thread
        self.allowed_to_invite = allowed_to_invite if allowed_to_invite else []
        self.allowed_to_chat = allowed_to_chat
        self.system_prompt = system_prompt
        self.log_full_response = log_full_response
        self.injected_system_prompt = injected_system_prompt

    async def message(self, room: MatrixRoom, event: RoomMessageText) -> None:
        """Callback for when a message event is received

        Args:
            room: The room the event came from.

            event: The event defining the message.
        """
        # Extract the message text
        msg = event.body.strip().strip('\n')

        logger.debug(f"Bot message received for room {room.display_name} | "
                     f"{room.user_name(event.sender)}: {msg}")

        await self.client.room_read_markers(room.room_id, event.event_id, event.event_id)

        # Ignore messages from ourselves
        if event.sender == self.client.user_id:
            return

        if not check_authorized(event.sender, self.allowed_to_chat):
            return

        if event.server_timestamp < self.startup_ts:
            logger.info(f'Skipping event as it was sent before startup time: {event.event_id}')
            return

        # if room.member_count > 2:
        #     has_command_prefix =
        # else:
        #     has_command_prefix = False

        # room.is_group is often a DM, but not always.
        # room.is_group does not allow room aliases
        # room.member_count > 2 ... we assume a public room
        # room.member_count <= 2 ... we assume a DM
        # General message listener
        if not msg.startswith(f'{self.command_prefix} ') and is_thread(event) and not self.store.check_seen_event(event.event_id) and (await is_this_our_thread(self.client, room, event, self.command_prefix)):
            await self.client.room_typing(room.room_id, typing_state=True, timeout=3000)
            thread_content = await get_thread_content(self.client, room, event)
            api_data = []
            for event in thread_content:
                if isinstance(event, MegolmEvent):
                    resp = await send_text_to_room(self.client, room.room_id, '❌ 🔐 Decryption Failure', reply_to_event_id=event.event_id, thread=True, thread_root_id=thread_content[0].event_id)
                    logger.critical(f'Decryption failure for event {event.event_id} in room {room.room_id}')
                    await self.client.room_typing(room.room_id, typing_state=False, timeout=3000)
                    self.store.add_event_id(resp.event_id)
                    return
                else:
                    thread_msg = event.body.strip().strip('\n')
                    api_data.append({'role': 'assistant' if event.sender == self.client.user_id else 'user', 'content': thread_msg if not thread_msg.startswith(self.command_prefix) else thread_msg[
                                                                                                                                                                                          len(self.command_prefix):].strip()})  # if len(thread_content) >= 2 and thread_content[0].body.startswith(self.command_prefix):  # if thread_content[len(thread_content) - 2].sender == self.client.user

            # message = Message(self.client, self.store, msg, room, event, self.reply_in_thread)
            # await message.process()
            # api_data.append({'role': 'user', 'content': msg})
            await process_chat(self.client, room, event, api_data, self.store, self.openai, thread_root_id=thread_content[0].event_id, system_prompt=self.system_prompt, log_full_response=self.log_full_response, injected_system_prompt=self.injected_system_prompt)
            return
        elif msg.startswith(f'{self.command_prefix} ') or room.member_count == 2:
            # Otherwise if this is in a 1-1 with the bot or features a command prefix, treat it as a command.
            msg = msg if not msg.startswith(self.command_prefix) else msg[len(self.command_prefix):].strip()  # Remove the command prefix
            command = Command(self.client, self.store, msg, room, event, self.openai, self.reply_in_thread, system_prompt=self.system_prompt, injected_system_prompt=self.injected_system_prompt, log_full_response=self.log_full_response)
            await command.process()

    async def invite(self, room: MatrixRoom, event: InviteMemberEvent) -> None:
        """Callback for when an invite is received. Join the room specified in the invite.

        Args:
            room: The room that we are invited to.

            event: The invite event.
        """
        if not check_authorized(event.sender, self.allowed_to_invite):
            logger.info(f"Got invite to {room.room_id} from {event.sender} but rejected.")
            return

        # if event.sender not in self.allowed_to_invite:
        #     logger.info(f"Got invite to {room.room_id} from {event.sender} but rejected.")
        #     return

        logger.debug(f"Got invite to {room.room_id} from {event.sender}.")

        # Attempt to join 3 times before giving up
        for attempt in range(3):
            result = await self.client.join(room.room_id)
            if type(result) == JoinError:
                logger.error(f"Error joining room {room.room_id} (attempt %d): %s", attempt, result.message, )
            else:
                break
        else:
            logger.error("Unable to join room: %s", room.room_id)

        # Successfully joined room
        logger.info(f"Joined via invite: {room.room_id}")

    async def invite_event_filtered_callback(self, room: MatrixRoom, event: InviteMemberEvent) -> None:
        """
        Since the InviteMemberEvent is fired for every m.room.member state received
        in a sync response's `rooms.invite` section, we will receive some that are
        not actually our own invite event (such as the inviter's membership).
        This makes sure we only call `callbacks.invite` with our own invite events.
        """
        if event.state_key == self.client.user_id:
            # This is our own membership (invite) event
            await self.invite(room, event)

    # async def _reaction(
    #         self, room: MatrixRoom, event: UnknownEvent, reacted_to_id: str
    # ) -> None:
    #     """A reaction was sent to one of our messages. Let's send a reply acknowledging it.
    #
    #     Args:
    #         room: The room the reaction was sent in.
    #
    #         event: The reaction event.
    #
    #         reacted_to_id: The event ID that the reaction points to.
    #     """
    #     logger.debug(f"Got reaction to {room.room_id} from {event.sender}.")
    #
    #     # Get the original event that was reacted to
    #     event_response = await self.client.room_get_event(room.room_id, reacted_to_id)
    #     if isinstance(event_response, RoomGetEventError):
    #         logger.warning(
    #             "Error getting event that was reacted to (%s)", reacted_to_id
    #         )
    #         return
    #     reacted_to_event = event_response.event
    #
    #     # Only acknowledge reactions to events that we sent
    #     if reacted_to_event.sender != self.config.user_id:
    #         return
    #
    #     # Send a message acknowledging the reaction
    #     reaction_sender_pill = make_pill(event.sender)
    #     reaction_content = (
    #         event.source.get("content", {}).get("m.relates_to", {}).get("key")
    #     )
    #     message = (
    #         f"{reaction_sender_pill} reacted to this event with `{reaction_content}`!"
    #     )
    #     await send_text_to_room(
    #         self.client,
    #         room.room_id,
    #         message,
    #         reply_to_event_id=reacted_to_id,
    #     )

    async def decryption_failure(self, room: MatrixRoom, event: MegolmEvent) -> None:
        """Callback for when an event fails to decrypt. Inform the user.

        Args:
            room: The room that the event that we were unable to decrypt is in.

            event: The encrypted event that we were unable to decrypt.
        """
        # logger.error(f"Failed to decrypt event '{event.event_id}' in room '{room.room_id}'!"
        #              f"\n\n"
        #              f"Tip: try using a different device ID in your config file and restart."
        #              f"\n\n"
        #              f"If all else fails, delete your store directory and let the bot recreate "
        #              f"it (your reminders will NOT be deleted, but the bot may respond to existing "
        #              f"commands a second time).")

        if event.server_timestamp > self.startup_ts:
            logger.critical(f'Decryption failure for event {event.event_id} in room {room.room_id}')
            await react_to_event(self.client, room.room_id, event.event_id, "❌ 🔐")

    async def unknown(self, room: MatrixRoom, event: UnknownEvent) -> None:
        """Callback for when an event with a type that is unknown to matrix-nio is received.
        Currently this is used for reaction events, which are not yet part of a released
        matrix spec (and are thus unknown to nio).

        Args:
            room: The room the reaction was sent in.

            event: The event itself.
        """
        # if event.type == "m.reaction":
        #     # Get the ID of the event this was a reaction to
        #     relation_dict = event.source.get("content", {}).get("m.relates_to", {})
        #
        #     reacted_to = relation_dict.get("event_id")
        #     if reacted_to and relation_dict.get("rel_type") == "m.annotation":
        #         await self._reaction(room, event, reacted_to)
        #         return

        logger.debug(f"Got unknown event with type to {event.type} from {event.sender} in {room.room_id}.")
