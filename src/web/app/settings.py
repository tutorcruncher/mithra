from pathlib import Path

from shared.settings import PgSettings

THIS_DIR = Path(__file__).parent
BASE_DIR = THIS_DIR.parent


class Settings(PgSettings):
    pass
