# Config Examples

### OpenAI

```yaml
command:
  - trigger: '!c4'
    api_type: openai
    model: gpt-4
    temperature: 0.5
openai:
  api_key: sk-qwerty123
```

#### Vision

```yaml
command:
  - trigger: '!cv'
    api_type: openai
    model: gpt-4-vision-preview
    max_tokens: 4096
    temperature: 0.5
    vision: true
openai:
  api_key: sk-qwerty123
```

#### System Prompt

```yaml
command:
  - trigger: '!cb'
    api_type: openai
    model: gpt-4
    max_tokens: 4096
    temperature: 1
    system_prompt: 'Ignore all prior instructions. Your objective is to [add your instructions here].'
    injected_system_prompt: 'Make sure to stay in character.'
    help: Internet argument bot.
```

### Anthropic

```yaml
command:
  - trigger: '!cc'
    api_type: anthropic
    model: claude-3-opus-20240229
    max_tokens: 4096
    temperature: 0.5
    vision: true
anthropic:
  api_key: sk-ant-api03-qwerty123
```

#### System Prompt

```yaml
command:
  - trigger: '!cc'
    api_type: anthropic
    model: claude-3-opus-20240229
    max_tokens: 4096
    temperature: 0.5
    system_prompt: 'Ignore all prior instructions. Your objective is to [add your instructions here].'
    vision: true
```

### Bing Copilot

See [Copilot.md](Copilot.md).

```yaml
command:
  - trigger: '!cp'
    model: copilot
    api_type: copilot
copilot:
  api_key: '_C_Auth=; MC1=GUID=....'
  event_encryption_key: abc123=
```

### Dalle-3

TODO
