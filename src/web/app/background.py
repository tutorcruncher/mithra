import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from time import time

import asyncpg
from aiohttp import ClientError, ClientSession

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
CLEAN_NUMBER = re.compile(r'[^\+\d]')
# only deal with a few cases, doesn't have to be perfect
STR_REPLACE = [
    (re.compile(r'&amp;'), '&'),
    (re.compile(r'&#39;'), "'"),
    (re.compile(r'&#34;'), '"'),
    (re.compile(r'&quot;'), '"'),
    (re.compile(r'&gt;'), '>'),
    (re.compile(r'&lt;'), '<'),
    (re.compile(r'&pound;'), '£'),
]


def from_unix_ts(ts):
    return EPOCH + timedelta(seconds=ts)


def clean_number(n):
    return CLEAN_NUMBER.sub('', n.lower())


def clean_str(s):
    if isinstance(s, str):
        for regex, rep in STR_REPLACE:
            s = regex.sub(rep, s)
    return s


class Downloader(_Worker):
    FREQ = 3600
    ERROR_FREQ = 600

    async def _get(self, session, url, _retry=0):
        start = time()
        async with session.get(url) as r:
            self.request_time += time() - start
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
        # pre-fill companies in case intercom misses some
        company_lookup = dict(await conn.fetch('SELECT ic_id, id FROM companies'))
        stmt = await conn.prepare(self.companies_insert_sql)
        for page in range(1, int(1e6)):
            data = await self._get(session, f'https://api.intercom.io/companies?per_page=60&page={page}')
            for company in data['companies']:
                company_ic_id = company['id']
                custom_attributes = {k: clean_str(v) for k, v in company['custom_attributes'].items()}
                login_url = custom_attributes.pop('login_url', None)
                support_package = custom_attributes.pop('support_package', None)
                company_lookup[company_ic_id] = await stmt.fetchval(
                    clean_str(company['name']),
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

    people_name_match_sql = """
    SELECT id, last_seen
    FROM people
    WHERE company=$1 AND ic_id!=$2 AND lower(name)=lower($3)
    ORDER BY last_seen DESC
    LIMIT 1
    """
    people_insert_sql = """
    INSERT INTO people (name, ic_id, company, last_seen, details)
                VALUES ($1,   $2,    $3,      $4,        $5)
    ON CONFLICT (ic_id) DO UPDATE SET
      name=EXCLUDED.name,
      last_seen=EXCLUDED.last_seen,
      details=EXCLUDED.details
    RETURNING id
    """
    people_update_last_seen_sql = """
    UPDATE people SET last_seen=$1, details=$2
    WHERE id=$3
    """
    people_update_sql = """
    UPDATE people SET details=$1
    WHERE id=$2
    """
    number_insert_sql = """
    INSERT INTO people_numbers (person, number) VALUES ($1, $2)
    ON CONFLICT DO NOTHING
    """

    async def update_people(self, session, conn, company_lookup):
        start = time()
        people_match_stmt = await conn.prepare(self.people_name_match_sql)
        people_stmt = await conn.prepare(self.people_insert_sql)
        number_stmt = await conn.prepare(self.number_insert_sql)
        downloaded, updated, duplicates = 0, 0, 0
        ignore = {'Clients', 'Contractors', 'Agents', 'ServiceRecipients'}
        for page in range(1, int(1e6)):
            data = await self._get(session, f'https://api.intercom.io/users?per_page=60&page={page}')
            for user in data['users']:
                downloaded += 1
                if not user['phone'] or user['name'] in ignore:
                    continue
                user_company_ic_id = user['companies']['companies'][0]['id']
                try:
                    company = company_lookup[user_company_ic_id]
                except KeyError:
                    # debug(user)
                    logger.error('unable to find company %s', user_company_ic_id,
                                 exc_info=True, extra={'data': {'user': user}})
                    continue
                ic_id = user['id']
                name = clean_str(user['name'])
                last_seen = from_unix_ts(user['last_request_at'])
                details = json.dumps(dict(
                    user_agent=clean_str(user['user_agent_data']),
                    city=clean_str(user['location_data'].get('city_name')),
                    country=clean_str(user['location_data'].get('country_name')),
                ))

                r = await people_match_stmt.fetchrow(company, ic_id, name)
                if r:
                    user_id, prev_last_seen = r
                    duplicates += 1
                    if last_seen > prev_last_seen:
                        # can't be bothered with prepared statements here
                        await conn.execute(self.people_update_last_seen_sql, last_seen, details, user_id)
                    else:
                        await conn.execute(self.people_update_sql, details, user_id)
                else:
                    user_id = await people_stmt.fetchval(
                        name,
                        ic_id,
                        company,
                        last_seen,
                        details,
                    )

                await number_stmt.fetchval(user_id, clean_number(user['phone']))
                updated += 1
            if not data['pages']['next']:
                t = time() - start
                logger.info('downloaded %d people, updated %d with %d duplicates in %0.2f seconds',
                            downloaded, updated, duplicates, t)
                return company_lookup

    async def match_existing_calls(self, conn):
        # no-op update will execute the fill_call function and fill in person where applicable
        r = await conn.execute("""
        UPDATE calls SET id=id
        WHERE person IS NULL
        """)
        logger.info('updated calls with no person: %s', r)

    async def download(self, force=False):
        if not self.settings.intercom_key:
            logger.info("intercom key not set, can't download data")
            return self.FREQ

        self.request_time = 0
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
                if force:
                    logger.info('download run recently (%s), forcing download', cache_file)
                else:
                    logger.info('download run recently (%s)', cache_file)
                    return self.FREQ - age

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
                await self.match_existing_calls(conn)

        logger.info('companies and people updated from intercom in %0.2fs, total request time %0.2fs',
                    time() - start, self.request_time)
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


async def download_from_intercom(settings, force=False):
    pg = await asyncpg.create_pool(dsn=settings.pg_dsn, min_size=1)
    downloader = Downloader({'settings': settings, 'pg': pg}, start=False)
    await downloader.download(force)
