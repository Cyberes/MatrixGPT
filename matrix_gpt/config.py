import copy
from pathlib import Path
from types import NoneType

import bison
from bison.errors import SchemeValidationError

VALID_API_TYPES = ['openai', 'anthropic', 'copilot']

config_scheme = bison.Scheme(
    bison.Option('store_path', default='bot-store/', field_type=str),
    bison.DictOption('auth', scheme=bison.Scheme(
        bison.Option('username', field_type=str, required=True),
        bison.Option('password', field_type=str, required=True),
        bison.Option('homeserver', field_type=str, required=True),
        bison.Option('device_id', field_type=str, required=True),
    )),
    bison.ListOption('allowed_to_chat', member_type=str, default=['all']),
    bison.ListOption('allowed_to_thread', member_type=str, default=['all']),
    bison.ListOption('allowed_to_invite', member_type=str, default=['all']),
    bison.ListOption('autojoin_rooms', default=[]),
    bison.ListOption('blacklist_rooms', default=[]),
    bison.Option('response_timeout', default=120, field_type=int),
    bison.ListOption('command', required=True, member_scheme=bison.Scheme(
        bison.Option('trigger', field_type=str, required=True),
        bison.Option('api_type', field_type=str, choices=VALID_API_TYPES, required=True),
        bison.Option('model', field_type=str, required=True),
        bison.Option('max_tokens', field_type=int, default=0),
        bison.Option('temperature', field_type=[int, float], default=0.5),
        bison.ListOption('allowed_to_chat', member_type=str, default=[]),
        bison.ListOption('allowed_to_thread', member_type=str, default=[]),
        bison.ListOption('allowed_to_invite', member_type=str, default=[]),
        bison.Option('system_prompt', field_type=str, default=None),
        bison.Option('injected_system_prompt', field_type=str, default=None),
        bison.Option('api_base', field_type=[str, NoneType], default=None),
        bison.Option('vision', field_type=bool, default=False),
        bison.Option('help', field_type=[str, NoneType], default=None),
    )),
    bison.DictOption('openai', scheme=bison.Scheme(
        bison.Option('api_key', field_type=[str, NoneType], default=None, required=False),
    )),
    bison.DictOption('anthropic', scheme=bison.Scheme(
        bison.Option('api_key', field_type=[str, NoneType], required=False, default=None),
    )),
    bison.DictOption('copilot', scheme=bison.Scheme(
        bison.Option('api_key', field_type=[str, NoneType], required=False, default=None),
    )),
    bison.DictOption('logging', scheme=bison.Scheme(
        bison.Option('log_level', field_type=str, default='info'),
        bison.Option('log_full_response', field_type=bool, default=True),
    )),
)
# Bison does not support list default options in certain situations.
# Only one level recursive.
DEFAULT_LISTS = {
    'command': {
        'max_tokens': 0,
        'temperature': 0.5,
        'allowed_to_chat': [],
        'allowed_to_thread': [],
        'allowed_to_invite': [],
        'system_prompt': None,
        'injected_system_prompt': None,
        'api_base': None,
        'vision': False,
        'help': None,
    }
}


class ConfigManager:
    def __init__(self):
        self._config = bison.Bison(scheme=config_scheme)
        self._command_prefixes = {}
        self._parsed_config = {}
        self._loaded = False
        self._validated = False

    def load(self, path: Path):
        assert not self._loaded
        self._config.config_name = 'config'
        self._config.config_format = bison.bison.YAML
        self._config.add_config_paths(str(path.parent))
        self._config.parse()
        self._loaded = True

    def validate(self):
        assert not self._validated
        self._config.validate()
        config_api_keys = 0
        for api in VALID_API_TYPES:
            if self._config.config[api].get('api_key'):
                config_api_keys += 1
        if config_api_keys < 1:
            raise SchemeValidationError('You need an API key')
        self._parsed_config = self._merge_in_list_defaults()

        for item in self._config.config['command']:
            if item['api_type'] == 'copilot' and item['model'] != 'copilot':
                raise SchemeValidationError('The Copilot model type must be set to `copilot`')

        # Make sure there aren't duplicate triggers
        existing_triggers = []
        for item in self._config.config['command']:
            trigger = item['trigger']
            if trigger in existing_triggers:
                raise SchemeValidationError(f'Duplicate trigger {trigger}')
            existing_triggers.append(trigger)

        self._command_prefixes = self._generate_command_prefixes()

    def _merge_in_list_defaults(self):
        new_config = copy.copy(self._config.config)
        for d_k, d_v in DEFAULT_LISTS.items():
            for k, v in self._config.config.items():
                if k == d_k:
                    assert isinstance(v, list)
                    new_list = []
                    for e in v:
                        merged_dict = copy.copy(d_v)  # create a copy of the default dict
                        merged_dict.update(e)  # update it with the new values
                        new_list.append(merged_dict)
                    new_config[k] = new_list
        return new_config

    @property
    def config(self):
        return copy.copy(self._parsed_config)

    def _generate_command_prefixes(self):
        assert not self._validated
        command_prefixes = {}
        for item in self._parsed_config['command']:
            command_prefixes[item['trigger']] = item
            if item['api_type'] == 'anthropic' and item.get('max_tokens', 0) < 1:
                raise SchemeValidationError(f'Anthropic requires `max_tokens`. See <https://support.anthropic.com/en/articles/7996856-what-is-the-maximum-prompt-length>')

        return command_prefixes

    @property
    def command_prefixes(self):
        return self._command_prefixes

    def get(self, key, default=None):
        return copy.copy(self._config.get(key, default))

    def __setitem__(self, key, item):
        raise Exception

    def __getitem__(self, key):
        return self._parsed_config[key]

    def __repr__(self):
        return repr(self._parsed_config)

    def __len__(self):
        return len(self._parsed_config)

    def __delitem__(self, key):
        raise Exception


global_config = ConfigManager()
