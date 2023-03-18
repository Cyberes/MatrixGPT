import logging

from nio import AsyncClient, MatrixRoom, RoomMessageText

from .chat_functions import get_thread_content, process_chat, send_text_to_room
# from .config import Config
from .storage import Storage

logger = logging.getLogger('MatrixGPT')


class Command:
    def __init__(
            self,
            client: AsyncClient,
            store: Storage,
            # config: Config,
            command: str,
            room: MatrixRoom,
            event: RoomMessageText,
            openai,
            reply_in_thread
    ):
        """A command made by a user.

        Args:
            client: The client to communicate to matrix with.

            store: Bot storage.

            config: Bot configuration parameters.

            command: The command and arguments.

            room: The room the command was sent in.

            event: The event describing the command.
        """
        self.client = client
        self.store = store
        # self.config = config
        self.command = command
        self.room = room
        self.event = event
        self.args = self.command.split()[1:]
        self.openai = openai
        self.reply_in_thread = reply_in_thread

    async def process(self):
        """Process the command"""
        # await self.client.room_read_markers(self.room.room_id, self.event.event_id, self.event.event_id)
        self.command = self.command.strip()
        # if self.command.startswith("echo"):
        #     await self._echo()
        # elif self.command.startswith("react"):
        #     await self._react()
        if self.command.startswith("help"):
            await self._show_help()
        else:
            await self._process_chat()

    async def _process_chat(self):
        await process_chat(self.client, self.room, self.event, self.command, self.store, self.openai)

    async def _show_help(self):
        """Show the help text"""
        # if not self.args:
        #     text = (
        #         "Hello, I am a bot made with matrix-nio! Use `help commands` to view "
        #         "available commands."
        #     )
        #     await send_text_to_room(self.client, self.room.room_id, text)
        #     return

        # topic = self.args[0]
        # if topic == "rules":
        #     text = "These are the rules!"
        # elif topic == "commands":
        #     text = """Available commands:"""
        # else:
        #     text = "Unknown help topic!"

        text = 'Send your message to ChatGPT like this: `!c Hi ChatGPT, how are you?`'

        await send_text_to_room(self.client, self.room.room_id, text)

    async def _unknown_command(self):
        await send_text_to_room(
            self.client,
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
        )
