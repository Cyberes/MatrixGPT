from matrix_gpt.config import global_config, VALID_API_TYPES


class CommandInfo:
    def __init__(self, trigger: str, api_type: str, model: str, max_tokens: int, temperature: float, allowed_to_chat: list, allowed_to_thread: list, allowed_to_invite: list, system_prompt: str, injected_system_prompt: str, api_base: str = None, vision: bool = False, help: str = None):
        self.trigger = trigger
        assert api_type in VALID_API_TYPES
        self.api_type = api_type
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.system_prompt = system_prompt
        self.injected_system_prompt = injected_system_prompt
        self.api_base = api_base
        self.vision = vision
        self.help = help

        self.allowed_to_chat = allowed_to_chat
        if not len(self.allowed_to_chat):
            self.allowed_to_chat = global_config['allowed_to_chat']

        self.allowed_to_thread = allowed_to_thread
        if not len(self.allowed_to_thread):
            self.allowed_to_thread = global_config['allowed_to_thread']

        self.allowed_to_invite = allowed_to_invite
        if not len(self.allowed_to_invite):
            self.allowed_to_invite = global_config['allowed_to_invite']
