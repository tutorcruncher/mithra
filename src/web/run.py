#!/usr/bin/env python3.6
import asyncio
import logging.config
import sys
from pathlib import Path

from aiohttp import ClientSession, web

THIS_DIR = Path(__file__).parent
if not Path(THIS_DIR / 'shared').exists():
    # when running outside docker
    sys.path.append(str(THIS_DIR / '..'))

from shared.logs import setup_logging  # NOQA
from app.main import create_app  # NOQA
from app.patch import reset_database, run_patch  # NOQA
from app.settings import Settings  # NOQA


logger = logging.getLogger('mithra.web.run')


async def _check(url):
    try:
        async with ClientSession() as session:
            async with session.get(url) as r:
                assert r.status == 200, f'response error {r.status} != 200'
    except (ValueError, AssertionError, OSError) as e:
        logger.error('web check error: %s: %s, url: "%s"', e.__class__.__name__, e, url)
        return 1
    else:
        logger.info('web check successful')


def check():
    loop = asyncio.get_event_loop()
    exit_code = loop.run_until_complete(_check('http://127.0.0.1:8000'))
    if exit_code:
        exit(exit_code)


if __name__ == '__main__':
    setup_logging()
    settings = Settings()
    try:
        _, command, *args = sys.argv
    except ValueError:
        print('no command provided, options are: "check", "reset_database", "patch" or "web"')
        sys.exit(1)

    if command == 'check':
        print('running check...')
        check()
    elif command == 'reset_database':
        print('running reset_database...')
        reset_database(settings)
    elif command == 'patch':
        print('running patch...')
        live = '--live' in args
        if live:
            args.remove('--live')
        run_patch(settings, live, args[0] if args else None)
    elif command == 'web':
        print('running web server...')
        app = create_app(settings=settings)
        web.run_app(app, port=8000, shutdown_timeout=1, access_log=None, print=lambda *args: None)
    else:
        print(f'unknown command "{command}"')
        sys.exit(1)
