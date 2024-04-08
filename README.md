# MatrixGPT

_Chatbots for Matrix._

## Install

1. Install requirements:
    ```bash
    sudo apt install libolm-dev gcc python3-dev
    pip install -r requirements.txt
    ```
2. Copy `config.sample.yaml` to `config.yaml` and fill it out with your bot's Matrix auth and your API key(s).

[Pantalaimon](https://github.com/matrix-org/pantalaimon) is **required** for the bot to be able to talk in encrypted
rooms.

I included a sample Systemd service.

## Use

Invite your bot to a room.

Start a chat by prefixing your message with your trigger (for example, `!c`). The bot will create a thread when it
replies to you and you don't need to use the trigger in the thread.

Don't try to use two bots in the same thread.

You can DM a bot for a private chat. Don't use the trigger prefix in a DM.

The bot will move its read marker when a new message is sent in the room.

The bot can give helpful reactions:

- 🚫 means that the user is not allowed to chat with the bot.
- ❌ means the bot encountered an exception. The bot restarts when it encounters an exception which means it will not be
  able to respond for a short time after this reaction.
- ❌ 🔐 means there was a decryption failure.

Use `!matrixgpt` to view the bot's help. The bot also responds to `!bots`.

## Encryption

This bot supports encryption. I recommend using [Pantalaimon](https://github.com/matrix-org/pantalaimon/) to manage
encryption keys as the built-in solution is a little janky and may be unreliable.
