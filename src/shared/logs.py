import logging
import os
import sys

from raven import Client

# from raven_aiohttp import AioHttpTransport


def setup_logging():
    """
    setup logging config by updating the arq logging config
    """
    verbose = '--verbose' in sys.argv
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
                'format': '%(levelname)-7s %(name)25s: %(message)s',
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
                'client': Client(
                    dsn=raven_dsn,
                    # https://github.com/getsentry/raven-aiohttp/issues/27
                    # transport=AioHttpTransport,
                    release=os.getenv('COMMIT', None),
                    name=os.getenv('IMAGE_NAME'),
                ),
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
