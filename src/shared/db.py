import asyncio
import logging

import asyncpg
from async_timeout import timeout

from .settings import PgSettings

logger = logging.getLogger('mithra.db')


async def lenient_conn(settings, with_db=True, _retry=0):
    if with_db:
        dsn = settings.pg_dsn
    else:
        dsn, _ = settings.pg_dsn.rsplit('/', 1)

    try:
        with timeout(2):
            conn = await asyncpg.connect(dsn=dsn)
    except asyncpg.CannotConnectNowError as e:
        if _retry < 5:
            logger.warning('pg temporary connection error %s, %d retries remaining...', e, 5 - _retry)
            await asyncio.sleep(2)
            return await lenient_conn(settings, _retry=_retry + 1)
        else:
            raise
    log = logger.info if _retry > 0 else logger.debug
    log('pg connection successful, version: %s', await conn.fetchval('SELECT version()'))
    return conn


DROP_CONNECTIONS = """
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = $1 AND pid <> pg_backend_pid();
"""


async def prepare_database(settings: PgSettings, overwrite_existing: bool) -> bool:
    """
    (Re)create a fresh database and run migrations.
    :param settings: settings to use for db connection
    :param overwrite_existing: whether or not to drop an existing database if it exists
    :return: whether or not a database has been (re)created
    """
    conn = await lenient_conn(settings, with_db=False)
    try:
        await conn.execute(DROP_CONNECTIONS, settings.pg_name)
        if not overwrite_existing:
            # this check is technically unnecessary but avoids an ugly postgres error log
            exists = await conn.fetchval('SELECT 1 AS result FROM pg_database WHERE datname=$1', settings.pg_name)
            if exists:
                logger.info('database already exists ✓')
                return False

        logger.debug('attempting to create database "%s"...', settings.pg_name)
        try:
            await conn.execute('CREATE DATABASE {}'.format(settings.pg_name))
        except (asyncpg.DuplicateDatabaseError, asyncpg.UniqueViolationError):
            if not overwrite_existing:
                logger.info('database already exists, skipping creation')
                return False
            else:
                logger.debug('database already exists...')
        else:
            logger.debug('database did not exist, now created')

        logger.debug('settings db timezone to utc...')
        await conn.execute(f"ALTER DATABASE {settings.pg_name} SET TIMEZONE TO 'UTC';")
    finally:
        await conn.close()

    conn = await asyncpg.connect(dsn=settings.pg_dsn)
    try:
        logger.debug('creating tables from model definition...')
        async with conn.transaction():
            await conn.execute(settings.models_sql)
    finally:
        await conn.close()
    logger.info('database successfully setup ✓')
    return True
