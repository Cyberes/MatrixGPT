# MatrixGPT

_ChatGPT bot for Matrix._

Uses code from [anoadragon453/nio-template](https://github.com/anoadragon453/nio-template).

## Install

```bash
sudo apt install libolm-dev gcc python3-dev
pip install -r requirements.txt
```

Copy `config.sample.yaml` to `config.yaml` and fill it out with your bot's auth and your OpenAI API key.

Then invite your bot and start a chat by prefixing your message with `!c`. The bot will create a thread (you don't need to use `!c` in the thread).

I included a sample Systemd service.

## Encryption

This bot supports encryption. I recommend using [Pantalaimon](https://github.com/matrix-org/pantalaimon/) to manage encryption keys as the
built-in solution is a little janky and may be unreliable. If you want a private DM with the bot I recommend creating a new room without encryption.