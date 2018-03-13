from pathlib import Path

from pydantic import BaseSettings
from pydantic.utils import make_dsn

THIS_DIR = Path(__file__).parent
BASE_DIR = THIS_DIR.parent


class PgSettings(BaseSettings):
    pg_name = 'mithra'
    pg_user = 'postgres'
    pg_password: str = None
    pg_host = 'localhost'
    pg_port = '5432'
    pg_driver = 'postgres'

    @property
    def pg_dsn(self) -> str:
        return make_dsn(
            driver=self.pg_driver,
            user=self.pg_user,
            password=self.pg_password,
            host=self.pg_host,
            port=self.pg_port,
            name=self.pg_name,
            query=None,
        )

    @property
    def models_sql(self):
        return (THIS_DIR / 'models.sql').read_text()
