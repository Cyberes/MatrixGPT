import asyncio
import logging
from types import ModuleType

from nio import AsyncClient, MatrixRoom, RoomMessageText

from .chat_functions import process_chat, react_to_event, send_text_to_room
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
            openai_obj: ModuleType,
            openai_model: str,
            reply_in_thread,
            openai_temperature: float = 0,
            system_prompt: str = None,
            injected_system_prompt: str = None,
            log_full_response: bool = False
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
        self.openai_model = openai_model
        self.reply_in_thread = reply_in_thread
        self.system_prompt = system_prompt
        self.injected_system_prompt = injected_system_prompt
        self.log_full_response = log_full_response
        self.openai_obj = openai_obj
        self.openai_temperature = openai_temperature

    async def process(self):
        """Process the command"""
        await self.client.room_read_markers(self.room.room_id, self.event.event_id, self.event.event_id)
        self.command = self.command.strip()
        # if self.command.startswith("echo"):
        #     await self._echo()
        # elif self.command.startswith("react"):
        #     await self._react()
        # if self.command.startswith("help"):
        #     await self._show_help()
        # else:
        try:
            await self._process_chat()
        except Exception:
            await react_to_event(self.client, self.room.room_id, self.event.event_id, '❌')
            raise

    async def _process_chat(self):
        async def inner():
            await process_chat(
                self.client,
                self.room,
                self.event,
                self.command,
                self.store,
                openai_obj=self.openai_obj,
                openai_model=self.openai_model,
                openai_temperature=self.openai_temperature,
                system_prompt=self.system_prompt,
                injected_system_prompt=self.injected_system_prompt,
                log_full_response=self.log_full_response
            )

        asyncio.get_event_loop().create_task(inner())

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
