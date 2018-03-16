from pathlib import Path

from shared.settings import PgSettings

THIS_DIR = Path(__file__).parent
BASE_DIR = THIS_DIR.parent


class Settings(PgSettings):
    google_siw_client_key = '421181039733-sdkjn7bclc9qgvk9a6iqrah0v3fk4aa5.apps.googleusercontent.com'
    auth_key = b'R60Wdn84EzcTuP4YQxvAAgiDlyNgl38keTVysTDdr2g='
    intercom_key: str = None
    cache_dir: str = '/tmp/mithra'


