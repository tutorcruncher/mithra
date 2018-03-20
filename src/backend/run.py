#!/usr/bin/env python3.6
import logging.config
import sys
from pathlib import Path
from time import time, sleep

THIS_DIR = Path(__file__).parent
if not Path(THIS_DIR / 'shared').exists():
    # when running outside docker
    sys.path.append(str(THIS_DIR / '..'))

from shared.logs import setup_logging  # NOQA
from main import Settings, main  # NOQA


logger = logging.getLogger('mithra.backend.run')


def check():
    settings = Settings()
    sentinal_file = Path(settings.cache_dir) / settings.sentinel_file
    # so first check is unlikely to fail
    sleep(2)
    if not sentinal_file.exists():
        logger.critical('sentinel file %s does not exist', sentinal_file)
        sys.exit(1)
    age = int(time() - sentinal_file.stat().st_mtime)
    if age > settings.register_expires:
        logger.critical('sentinel file has expired, age: %ds', age)
        sys.exit(1)
    else:
        logger.info('sentinel file ok, age: %ds', age)


if __name__ == '__main__':
    setup_logging(disable_existing=True)
    if 'check' in sys.argv:
        check()
    else:
        main()
