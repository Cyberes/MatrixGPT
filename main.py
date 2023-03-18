#!/usr/bin/env python3
import argparse
import asyncio
import logging
import os
import sys
import time
import traceback
from pathlib import Path

import openai
import yaml
from aiohttp import ClientConnectionError, ServerDisconnectedError
from nio import InviteMemberEvent, JoinResponse, LocalProtocolError, MegolmEvent, RoomMessageText

from matrix_gpt import MatrixNioGPTHelper
from matrix_gpt.bot.callbacks import Callbacks
from matrix_gpt.bot.storage import Storage
from matrix_gpt.config import check_config_value_exists

script_directory = os.path.abspath(os.path.dirname(__file__))

logging.basicConfig()
logger = logging.getLogger('MatrixGPT')
logger.setLevel(logging.INFO)

parser = argparse.ArgumentParser(description='MatrixGPT Bot')
parser.add_argument('--config', default=Path(script_directory, 'config.yaml'), help='Path to config.yaml if it is not located next to this executable.')
args = parser.parse_args()

# Load config
if not Path(args.config).exists():
    print('Config file does not exist:', args.config)
    sys.exit(1)
else:
    try:
        with open(args.config, 'r') as file:
            config_data = yaml.safe_load(file)
    except Exception as e:
        print(f'Failed to load config file: {e}')
        sys.exit(1)

# Test config
check_config_value_exists(config_data, 'bot_auth', dict)
check_config_value_exists(config_data['bot_auth'], 'username')
check_config_value_exists(config_data['bot_auth'], 'password')
check_config_value_exists(config_data['bot_auth'], 'homeserver')
check_config_value_exists(config_data['bot_auth'], 'store_path')
check_config_value_exists(config_data, 'allowed_to_chat')
check_config_value_exists(config_data, 'allowed_to_invite', allow_empty=True)
check_config_value_exists(config_data, 'command_prefix')
check_config_value_exists(config_data, 'openai_api_key')
check_config_value_exists(config_data, 'openai_model')
check_config_value_exists(config_data, 'data_storage')


# check_config_value_exists(config_data, 'autojoin_rooms')

def retry(msg=None):
    if msg:
        logger.warning(f'{msg}, retrying in 15s...')
    else:
        logger.warning(f'Retrying in 15s...')
    time.sleep(15)


async def main():
    matrix_helper = MatrixNioGPTHelper(
        auth_file=Path(config_data['bot_auth']['store_path'], 'bot_auth.json'),
        user_id=config_data['bot_auth']['username'],
        passwd=config_data['bot_auth']['password'],
        homeserver=config_data['bot_auth']['homeserver'],
        store_path=config_data['bot_auth']['store_path'],
        device_id=config_data['bot_auth'].get('device_id')
    )
    client = matrix_helper.client

    openai.api_key = config_data['openai_api_key']

    openai_config = {
        'model': config_data['openai_model'],
        'openai': openai
    }

    storage = Storage(Path(config_data['data_storage'], 'matrixgpt.db'))

    # Set up event callbacks
    callbacks = Callbacks(client, storage, config_data['command_prefix'], openai_config, config_data.get('reply_in_thread', False), config_data['allowed_to_invite'], config_data['allowed_to_chat'])
    client.add_event_callback(callbacks.message, RoomMessageText)
    client.add_event_callback(callbacks.invite_event_filtered_callback, InviteMemberEvent)
    client.add_event_callback(callbacks.decryption_failure, MegolmEvent)
    # client.add_event_callback(callbacks.unknown, UnknownEvent)

    # Keep trying to reconnect on failure (with some time in-between)
    while True:
        try:
            # Try to login with the configured username/password
            try:
                login_response = await matrix_helper.login()

                # Check if login failed
                if not login_response[0]:
                    logger.error(f'Failed to login: {login_response[1].message}\n{vars(login_response[1])}')
                    retry()
                    return False
            except LocalProtocolError as e:
                # There's an edge case here where the user hasn't installed the correct C
                # dependencies. In that case, a LocalProtocolError is raised on login.
                logger.fatal(f'Failed to login:\n{e}')
                retry()
                return False

            # Login succeeded!
            logger.info(f"Logged in as {client.user_id}")
            if config_data.get('autojoin_rooms'):
                for room in config_data.get('autojoin_rooms'):
                    r = await client.join(room)
                    if not isinstance(r, JoinResponse):
                        logger.critical(f'Failed to join room {room}: {vars(r)}')

            await client.sync_forever(timeout=10000, full_state=True)
        except (ClientConnectionError, ServerDisconnectedError):
            logger.warning("Unable to connect to homeserver, retrying in 15s...")
            time.sleep(15)
        finally:
            await client.close()
            sys.exit()


if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except Exception:
            logger.critical(traceback.format_exc())
            time.sleep(5)
