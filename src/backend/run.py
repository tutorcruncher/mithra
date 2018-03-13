#!/usr/bin/env python3.6
import logging
import logging.config
import os
import sys
from pathlib import Path

from main import main  # NOQA

THIS_DIR = Path(__file__).parent
if not Path(THIS_DIR / 'shared').exists():
    # when running outside docker
    sys.path.append(str(THIS_DIR / '..'))


logger = logging.getLogger('mithra.backend.run')


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
                'format': '%(levelname)s %(name)s %(message)s',
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


def check():
    logger.warning('TODO check')


if __name__ == '__main__':
    verbose = '--verbose' in sys.argv
    setup_logging(verbose)
    if 'check' in sys.argv:
        check()
    else:
        main()
