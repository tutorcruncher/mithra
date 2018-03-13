#!/usr/bin/env python3.6
import asyncio
import logging
import logging.config
import os
import sys
from pathlib import Path

from aiohttp import ClientSession, web

from app.main import create_app  # NOQA
from app.patch import reset_database, run_patch  # NOQA
from app.settings import Settings  # NOQA

THIS_DIR = Path(__file__).parent
if not Path(THIS_DIR / 'shared').exists():
    # when running outside docker
    sys.path.append(str(THIS_DIR / '..'))


logger = logging.getLogger('mithra.web.run')


def setup_logging(verbose: bool=False):
    """
    setup logging config by updating the arq logging config
    """
    log_level = 'DEBUG' if verbose else 'INFO'
    raven_dsn = os.getenv('RAVEN_DSN', None)
    if raven_dsn in ('', '-'):
        # thus setting an environment variable of "-" means no raven
        raven_dsn = None
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'mithra.default': {
                'format': '%(levelname)s %(name)20s: %(message)s',
            },
        },
        'handlers': {
            'mithra.default': {
                'level': log_level,
                'class': 'logging.StreamHandler',
                'formatter': 'mithra.default',
            },
            'sentry': {
                'level': 'WARNING',
                'class': 'raven.handlers.logging.SentryHandler',
                'dsn': raven_dsn,
                'release': os.getenv('COMMIT', None),
                'name': os.getenv('SERVER_NAME', '-')
            },
        },
        'loggers': {
            'mithra': {
                'handlers': ['mithra.default', 'sentry'],
                'level': log_level,
            },
        },
    }
    logging.config.dictConfig(config)


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
    url = 'http://' + os.getenv('BIND', '127.0.0.1:8000')
    loop = asyncio.get_event_loop()
    exit_code = loop.run_until_complete(_check(url))
    if exit_code:
        exit(exit_code)


if __name__ == '__main__':
    setup_logging('--verbose' in sys.argv)
    settings = Settings()
    if 'check' in sys.argv:
        print('running check...')
        check()
    if 'reset_database' in sys.argv:
        print('running reset_database...')
        reset_database(settings)
    if 'patch' in sys.argv:
        print('running patch...')
        args = list(sys.argv)
        print(args)
        live = '--live' in args
        if live:
            args.remove('--live')
        run_patch(settings, live, args[-1])
    else:
        print('running web server...')
        app = create_app(settings=settings)
        web.run_app(app, port=8000, access_log=None, print=lambda *args: None)
