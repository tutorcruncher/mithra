#!/usr/bin/env python3.6
import logging.config
import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent
if not Path(THIS_DIR / 'shared').exists():
    # when running outside docker
    sys.path.append(str(THIS_DIR / '..'))

from shared.logs import setup_logging  # NOQA
from main import main  # NOQA


logger = logging.getLogger('mithra.backend.run')


def check():
    logger.warning('TODO check')


if __name__ == '__main__':
    setup_logging()
    if 'check' in sys.argv:
        check()
    else:
        main()
