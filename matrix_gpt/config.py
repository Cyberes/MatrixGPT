import sys


def check_config_value_exists(config_part, key, check_type=None, allow_empty=False) -> bool:
    if key not in config_part.keys():
        print(f'Config key not found: "{key}"')
        sys.exit(1)
    if not allow_empty and config_part[key] is None or config_part[key] == '':
        print(f'Config key "{key}" must not be empty.')
        sys.exit(1)
    if check_type and not isinstance(config_part[key], check_type):
        print(f'Config key "{key}" must be type "{check_type}", not "{type(config_part[key])}".')
        sys.exit(1)
    return True
