#!/usr/bin/env python3
import argparse
import asyncio
import logging
import os
import signal
import sys
import time
import traceback
from pathlib import Path

from aiohttp import ClientConnectionError, ServerDisconnectedError
from bison.errors import SchemeValidationError
from nio import InviteMemberEvent, JoinResponse, MegolmEvent, RoomMessageText, UnknownEvent, RoomMessageImage

from matrix_gpt import MatrixClientHelper
from matrix_gpt.callbacks import MatrixBotCallbacks
from matrix_gpt.config import global_config

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))

logging.basicConfig()
logger = logging.getLogger('MatrixGPT')


async def main(args):
    args.config = Path(args.config)
    if not args.config.exists():
        logger.critical('Config file does not exist:', args.config)
        sys.exit(1)

    global_config.load(args.config)
    try:
        global_config.validate()
    except SchemeValidationError as e:
        logger.critical(f'Config validation error: {e}')
        sys.exit(1)

    if global_config['logging']['log_level'] == 'info':
        log_level = logging.INFO
    elif global_config['logging']['log_level'] == 'debug':
        log_level = logging.DEBUG
    elif global_config['logging']['log_level'] == 'warning':
        log_level = logging.WARNING
    elif global_config['logging']['log_level'] == 'critical':
        log_level = logging.CRITICAL
    else:
        log_level = logging.INFO
    logger.setLevel(log_level)

    l = logger.getEffectiveLevel()
    if l == 10:
        logger.debug('Log level is DEBUG')
    elif l == 20:
        logger.info('Log level is INFO')
    elif l == 30:
        logger.warning('Log level is WARNING')
    elif l == 40:
        logger.error('Log level is ERROR')
    elif l == 50:
        logger.critical('Log level is CRITICAL')
    else:
        logger.info(f'Log level is {l}')
    del l

    logger.debug(f'Command Prefixes: {[k for k, v in global_config.command_prefixes.items()]}')

    client_helper = MatrixClientHelper(
        user_id=global_config['auth']['username'],
        passwd=global_config['auth']['password'],
        homeserver=global_config['auth']['homeserver'],
        store_path=global_config['store_path'],
        device_id=global_config['auth']['device_id']
    )
    client = client_helper.client

    if global_config['openai'].get('api_base'):
        logger.info(f'Set OpenAI API base URL to: {global_config["openai"].get("api_base")}')

    # Set up event callbacks
    callbacks = MatrixBotCallbacks(client=client_helper)
    client.add_event_callback(callbacks.handle_message, (RoomMessageText, RoomMessageImage))
    client.add_event_callback(callbacks.handle_invite, InviteMemberEvent)
    client.add_event_callback(callbacks.decryption_failure, MegolmEvent)
    client.add_event_callback(callbacks.unknown, UnknownEvent)

    # Keep trying to reconnect on failure (with some time in-between)
    while True:
        try:
            logger.info('Logging in...')
            while True:
                login_success, login_response = await client_helper.login()
                if not login_success:
                    if 'M_LIMIT_EXCEEDED' in str(login_response):
                        try:
                            wait = int((int(str(login_response).split(' ')[-1][:-2]) / 1000) / 2)  # only wait half the ratelimited time
                            logger.error(f'Ratelimited, sleeping {wait}s...')
                            time.sleep(wait)
                        except:
                            logger.error(f'Could not parse M_LIMIT_EXCEEDED: {login_response}')
                    else:
                        logger.error(f'Failed to login, retrying: {login_response}')
                        time.sleep(5)
                else:
                    break

            # Login succeeded!
            logger.info(f'Logged in as {client.user_id}')
            if global_config.get('autojoin_rooms'):
                for room in global_config.get('autojoin_rooms'):
                    r = await client.join(room)
                    if not isinstance(r, JoinResponse):
                        logger.critical(f'Failed to join room {room}: {vars(r)}')
                    time.sleep(1.5)

            logger.info('Performing initial sync...')
            last_sync = (await client_helper.sync()).next_batch
            client_helper.run_sync_in_bg()  # start a background thread to record our sync tokens

            logger.info('Bot is active')
            await client.sync_forever(timeout=10000, full_state=True, since=last_sync)
        except (ClientConnectionError, ServerDisconnectedError):
            logger.warning("Unable to connect to homeserver, retrying in 15s...")
            time.sleep(15)
        except KeyboardInterrupt:
            await client.close()
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            logger.critical(traceback.format_exc())
            logger.critical('Sleeping 5s...')
            time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MatrixGPT Bot')
    parser.add_argument('--config', default=Path(SCRIPT_DIR, 'config.yaml'), help='Path to config.yaml if it is not located next to this executable.')
    args = parser.parse_args()

    while True:
        try:
            asyncio.run(main(args))
        except KeyboardInterrupt:
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            logger.critical(traceback.format_exc())
            time.sleep(5)
