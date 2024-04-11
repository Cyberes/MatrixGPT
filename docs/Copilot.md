# Copilot Setup

Copilot doesn't have a concept of "context". But the server does keep track of conversations.

The bot will store conversation metadata in the Matrix room attached to its initial response to a query. This metadata
is encrypted and contains the necessary information needed to load the conversation and continue talking to the user.

You need to generate your encryption key first:

```bash
python3 new-fernet-key.py
```

This will print a string. Copy this to your `config.yaml` in the `event_encryption_key` field in the `copilot` section.
