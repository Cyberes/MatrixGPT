# MatrixGPT

_Chatbots for Matrix._

This bot supports OpenAI, Anthropic, and locally hosted models that use an OpenAI-compatible endpoint. It can run
multiple different models using different triggers, such as `!c4` for GPT4 and `!ca` for Anthropic, all through the same bot.

**Supported Services**

- OpenAI (+ vision)
- Anthropic (+ vision)
- Anthropic
- Bing Copilot
- ~~Dalle-3~~ (TODO)

<br>

## Install

1. Install requirements:
    ```bash
    sudo apt install libolm-dev gcc python3-dev
    pip install -r requirements.txt
    ```
2. Copy `config.sample.yaml` to `config.yaml` and fill it out with the bot's Matrix authentication and your OpenAI
   and/or Anthropic API keys.
3. Start the bot with `python3 main.py`

[Pantalaimon](https://github.com/matrix-org/pantalaimon) is **required** for the bot to be able to talk in encrypted rooms.

If you are using Copilot, please read the extra documentation: [docs/Copilot.md](docs/Copilot.md)

I included a sample Systemd service (`matrixgpt.service`).

## Use

First, invite your bot to a room. Then you can start a chat by prefixing your message with your trigger (for
example, `!c hello!`). The bot will create a thread when it replies. You don't need to use the trigger in the thread.

Use `!matrixgpt` to view the bot's help. The bot also responds to `!bots`.

<br>

- Don't try to use two bots in the same thread.
- You can DM the bot for a private chat.
- The bot will move its read marker whenever a message is sent in the room.

<br>

The bot can give helpful reactions:

- 🚫 means permission denied (not allowed to chat with the bot).
- 🕒 means the API timed out.
- ❌ means the bot encountered an exception.
- ❌ 🔐 means there was a decryption failure.

## TODO

- [ ] Add our own context mechanism to Copilot
- [ ] Dalle bot
- [ ] Improve error messages sent with reactions to narrow down where the issue occurred.
- [ ] Allow replying to an image post which will give a vision model an image + text on the first message.
- [ ] Fix the typing indicator being removed when two responses are generating.
- [ ] ~~Add vision to Copilot~~ (not doing, API to unstable).
