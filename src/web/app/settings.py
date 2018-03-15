from pathlib import Path

from shared.settings import PgSettings

THIS_DIR = Path(__file__).parent
BASE_DIR = THIS_DIR.parent


class Settings(PgSettings):
    google_siw_client_key: str = '421181039733-sdkjn7bclc9qgvk9a6iqrah0v3fk4aa5.apps.googleusercontent.com'
    auth_key: bytes = b'R60Wdn84EzcTuP4YQxvAAgiDlyNgl38keTVysTDdr2g='
