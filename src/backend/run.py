#!/usr/bin/env python3.6
import asyncio
import logging.config
import sys
from pathlib import Path

import uvloop

THIS_DIR = Path(__file__).parent
if not Path(THIS_DIR / 'shared').exists():
    # when running outside docker
    sys.path.append(str(THIS_DIR / '..'))

from shared.logs import setup_logging  # NOQA
from main import main  # NOQA


logger = logging.getLogger('mithra.backend.run')


if __name__ == '__main__':
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    setup_logging()
    main()
