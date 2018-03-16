import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from time import time

import asyncpg
from aiohttp import ClientSession, ClientError

from .settings import Settings

logger = logging.getLogger('mithra.web.background')


class _Worker:
    def __init__(self, app, start=True):
        self.app = app
        self.settings: Settings = app['settings']
        self.running = True
        loop = asyncio.get_event_loop()
        if start:
            self.task = loop.create_task(self.run())

    async def run(self):
        raise NotImplementedError()

    async def close(self):
        logger.info('closing web background task')
        self.running = False
        await self.task
        self.task.result()


class WebsocketPropagator(_Worker):
    def __init__(self, app):
        super().__init__(app)
        self.websockets = set()

    def add_ws(self, ws):
        self.websockets.add(ws)

    def remove_ws(self, ws):
        try:
            self.websockets.remove(ws)
        except KeyError:
            pass

    async def run(self):
        pending_futures = set()

        def on_event(conn, pid, channel, payload):
            pending_futures.add(self._send(payload))

        while 'pg' not in self.app:
            await asyncio.sleep(0.1)
        channel = 'call'
        async with self.app['pg'].acquire() as conn:
            logger.info('web background task connecting to channel "%s"', channel)
            await conn.add_listener(channel, on_event)
            while True:
                await asyncio.sleep(0.1)
                if pending_futures:
                    _, pending_futures = await asyncio.wait(pending_futures)
                if not self.running:
                    break
            await conn.remove_listener(channel, on_event)

    async def _send(self, data):
        logger.info('sending %s to %d connected websockets', data, len(self.websockets))
        for ws in self.websockets:
            try:
                await ws.send_str(data)
            except (RuntimeError, AttributeError):
                logger.info(' ws "%s" closed, removing', ws)
                self.remove_ws(ws)


async def response_data(r):
    try:
        return await r.json()
    except (ClientError, ValueError):
        return await r.text()


EPOCH = datetime(1970, 1, 1)


def from_unix_ts(ts):
    return EPOCH + timedelta(seconds=ts)


class Downloader(_Worker):
    FREQ = 3600
    ERROR_FREQ = 600

    async def _get(self, session, url, _retry=0):
        async with session.get(url) as r:
            if r.status == 429 and _retry < 5:
                print('429, waiting 2 seconds...')
                await asyncio.sleep(2)
                return await self._get(session, url, _retry=_retry + 1)

            if r.status == 200:
                return await r.json()
            else:
                logger.error('unexpected response code from intercom %s', r.status, extra={
                    'data': {
                        'request_url': url,
                        'response_headers': dict(r.headers),
                        'response_data': await response_data(r),
                    }
                })
                raise RuntimeError(f'wrong response: {r.status}')

    companies_insert_sql = """
    INSERT INTO companies (name, ic_id, created, login_url, has_support, details) 
                   VALUES ($1,   $2,    $3,      $4,        $5,          $6)
    ON CONFLICT (ic_id) DO UPDATE SET 
      name=EXCLUDED.name, 
      created=EXCLUDED.created,
      login_url=EXCLUDED.login_url, 
      has_support=EXCLUDED.has_support,
      details=EXCLUDED.details
    RETURNING id
    """

    async def update_companies(self, session, conn):
        start = time()
        company_lookup = {}
        stmt = await conn.prepare(self.companies_insert_sql)
        for page in range(1, int(1e6)):
            data = await self._get(session, f'https://api.intercom.io/companies?per_page=60&page={page}')
            for company in data['companies']:
                company_ic_id = company['id']
                custom_attributes = dict(company['custom_attributes'])
                login_url = custom_attributes.pop('login_url', None)
                support_package = custom_attributes.pop('support_package', None)
                company_lookup[company_ic_id] = await stmt.fetchval(
                    company['name'],
                    company_ic_id,
                    from_unix_ts(company['created_at']),
                    login_url,
                    bool(support_package),
                    json.dumps(dict(
                        monthly_spend=company['monthly_spend'],
                        session_count=company['session_count'],
                        user_count=company['user_count'],
                        plan_name=company['plan'].get('name'),
                        **custom_attributes,
                    ))
                )
            if not data['pages']['next']:
                logger.info('updated %d companies in %0.2f seconds', len(company_lookup), time() - start)
                return company_lookup

    people_insert_sql = """
    INSERT INTO people (name, ic_id, company, last_seen, details) 
                VALUES ($1,   $2,    $3,      $4,        $5)
    ON CONFLICT (ic_id) DO UPDATE SET 
      name=EXCLUDED.name, 
      last_seen=EXCLUDED.last_seen,
      details=EXCLUDED.details
    RETURNING id
    """
    number_insert_sql = """
    INSERT INTO people_numbers (person, number) VALUES ($1, $2)
    ON CONFLICT DO NOTHING 
    """

    async def update_people(self, session, conn, company_lookup):
        start = time()
        people_stmt = await conn.prepare(self.people_insert_sql)
        number_stmt = await conn.prepare(self.number_insert_sql)
        updated = 0
        for page in range(1, int(1e6)):
            data = await self._get(session, f'https://api.intercom.io/users?per_page=60&page={page}')
            for user in data['users']:
                if not user['phone']:
                    continue
                try:
                    company = company_lookup[user['companies']['companies'][0]['id']]
                except KeyError:
                    logger.error('unable to find company for user %s', user)
                    raise
                user_id = await people_stmt.fetchval(
                    user['name'],
                    user['id'],
                    company,
                    from_unix_ts(user['last_request_at']),
                    json.dumps(dict(
                        user_agent=user['user_agent_data'],
                        city=user['location_data'].get('city_name'),
                        country=user['location_data'].get('country_name'),
                    ))
                )
                await number_stmt.fetchval(user_id, user['phone'])
                updated += 1
            if not data['pages']['next']:
                logger.info('updated %d people in %0.2f seconds', updated, time() - start)
                return company_lookup

    async def download(self):
        if not self.settings.intercom_key:
            logger.info("intercom key not set, can't download data")
            return self.FREQ

        start = time()
        cache_dir = Path(self.settings.cache_dir)
        cache_dir.mkdir(exist_ok=True, parents=True)
        cache_file = cache_dir / 'download_last_run.txt'
        try:
            age = int(start) - int(cache_file.read_text())
        except (FileNotFoundError, ValueError):
            pass
        else:
            if age < (self.FREQ - 60):
                run_in = self.FREQ - age
                logger.info('download run recently (%s)', cache_file)
                return run_in

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.settings.intercom_key}'
        }
        while 'pg' not in self.app:
            await asyncio.sleep(0.1)
        logger.info('running intercom download...')
        async with ClientSession(headers=headers) as session:
            async with self.app['pg'].acquire() as conn:
                company_lookup = await self.update_companies(session, conn)
                await self.update_people(session, conn, company_lookup)

        logger.info('companies and people updated from intercom in %0.2f seconds', time() - start)
        cache_file.write_text(f'{start:0.0f}')
        return self.FREQ

    async def run(self):
        while True:
            try:
                wait = await self.download()
            except Exception as e:
                logger.exception('Error running intercom downloader: %s', e)
                wait = self.ERROR_FREQ

            logger.info('waiting %0.0f seconds to run download', wait)
            for i in range(wait):
                await asyncio.sleep(1)
                if not self.running:
                    return


async def download_from_intercom(settings):
    pg = await asyncpg.create_pool(dsn=settings.pg_dsn)
    downloader = Downloader({'settings': settings, 'pg': pg}, start=False)
    await downloader.download()
