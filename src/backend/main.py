import asyncio
import hashlib
import logging
import re
import secrets
import signal
from pathlib import Path
from time import time
from typing import NamedTuple

import asyncpg
from async_timeout import timeout

from shared.db import lenient_conn
from shared.settings import PgSettings

try:
    from devtools import debug
except ImportError:
    def debug(*args, **kwargs):
        pass

logger = logging.getLogger('mithra.backend.main')


class Settings(PgSettings):
    sip_host: str
    sip_port: int = 5060
    sip_username: str
    sip_password: str
    cache_dir: str = '/tmp/mithra'
    sentinel_file: str = 'sentinel.txt'

    # expires time on register commands, will re-register every (register_expires - 1) seconds
    register_expires = 300

    @property
    def sip_uri(self):
        return f'sip:{self.sip_host}:{self.sip_password}'


REALM_REGEX = re.compile('realm="(.+?)"')
NONCE_REGEX = re.compile('nonce="(.+?)"')
RESPONSE_DECODE = re.compile(r'SIP/2.0 (?P<status_code>[0-9]{3}) (?P<status_message>.+)')
REQUEST_DECODE = re.compile(r'(?P<method>[A-Za-z]+) (?P<to_uri>.+) SIP/2.0')
FIND_BRANCH = re.compile(r'branch=(.+?);')
NUMBER = re.compile(r'sip:\+*([\d]+)@')


class Response(NamedTuple):
    status: int
    headers: dict
    response_data: bytes
    request_data: str


def parse_headers(raw_headers):
    headers = {}
    decoded_headers = raw_headers.decode().split('\r\n')
    for line in decoded_headers[1:]:
        k, v = line.split(': ', 1)
        if k in headers:
            headers[k] += '\n' + v
        else:
            headers[k] = v

    for regex in (RESPONSE_DECODE, REQUEST_DECODE):
        m = regex.match(decoded_headers[0])
        if m:
            return m.groupdict(), headers
    raise RuntimeError('unable to decode response headers')


def try_decode(data: bytes):
    try:
        data_text = data.decode()
    except UnicodeDecodeError as e:
        logger.warning('decode failed: %s', e)
        return data
    else:
        return data_text


def md5digest(*args):
    return hashlib.md5(':'.join(args).encode()).hexdigest()


class Database:
    def __init__(self, settings: Settings, loop):
        self.settings = settings
        self._pg = None
        self._loop = loop
        self.tasks = []

    async def init(self):
        conn = await lenient_conn(self.settings)
        await conn.close()
        self._pg = await asyncpg.create_pool(dsn=self.settings.pg_dsn, min_size=2)

    def record_call(self, number, country):
        self.tasks.append(self._loop.create_task(self._record_call(number, country)))

    async def _record_call(self, number, country):
        number = number.replace(' ', '').upper()
        await self._pg.execute('INSERT INTO calls (number, country) VALUES ($1, $2)', number, country)

    async def complete_tasks(self):
        if self.tasks:
            await asyncio.gather(*self.tasks)
            self.tasks = []

    async def close(self):
        await self.complete_tasks()
        await self._pg.close()


class SipProtocol:
    def __init__(self, connected_event, datagram_callback):
        self.connected_event = connected_event
        self.datagram_callback = datagram_callback

    def connection_made(self, transport):
        logger.info('connection established')
        self.connected_event.set()

    def datagram_received(self, data, addr):
        if data.startswith(b'\x00'):
            logger.debug('ping from server: %s (%s), ignoring', data, addr)
            return
        try:
            self.datagram_callback(data)
        except Exception as e:
            logger.exception('error processing datagram %s: %s', type(e), e, extra={
                'data': {
                    'datagram': try_decode(data),
                    'addr': addr
                }
            })

    def error_received(self, exc):
        logger.error('error received: %s', exc)

    def connection_lost(self, exc):
        if exc:
            logger.warning('connection lost: %s', exc)
        else:
            logger.debug('connection lost')


class SipClient:
    # time to wait before re-registering if an error occurred
    ERROR_WAIT = 30

    def __init__(self, settings: Settings, db: Database, loop):
        self.settings = settings
        self.db = db
        self.loop = loop
        self.transport = None
        self.local_ip = None
        self.cseq = 1
        self.request_lock = asyncio.Lock()
        self.request_future = None
        self.call_cache = {}
        self.task = None
        self.stopping = None

        cache_dir = Path(self.settings.cache_dir)
        cache_dir.mkdir(exist_ok=True, parents=True)
        cache_file = cache_dir / 'caller_id.txt'
        try:
            self.call_id = cache_file.read_text().strip(' \r\n')
        except FileNotFoundError:
            self.call_id = f'{secrets.token_hex()[:40]}@mithra'
            cache_file.write_text(self.call_id + '\n')
            logger.info('generated new Caller-ID: "%s", saved to %s', self.call_id, cache_file)
        else:
            logger.info('loaded Caller-ID from %s: "%s"', cache_file, self.call_id)
        self.sentinal_file = cache_dir / settings.sentinel_file

    async def start(self):
        self.task = self.loop.create_task(self.main_task())
        self.loop.add_signal_handler(signal.SIGINT, self.stop, 'sigint')
        self.loop.add_signal_handler(signal.SIGTERM, self.stop, 'sigterm')

    async def main_task(self):
        try:
            while True:
                if self.transport:
                    logger.info('un-registering and creating new transport...')
                    await self.register(expires=0)
                    self.transport.close()

                await self.connect_transport()
                for i in range(20):
                    try:
                        re_register = await self.register(expires=self.settings.register_expires)
                    except asyncio.TimeoutError:
                        logger.warning('timeout error registering', exc_info=True)
                        re_register = self.ERROR_WAIT
                    logger.info('re-registering in %d seconds', re_register)
                    start = time()
                    while True:
                        await asyncio.sleep(1)
                        await self.db.complete_tasks()
                        if self.stopping:
                            return
                        if (time() - start) > re_register:
                            break
        finally:
            logger.info('stopping reason: "%s", un-registering...', self.stopping)
            if self.transport:
                await self.register(expires=0)
                self.transport.close()
            await self.db.close()

    async def run_forever(self):
        await self.task

    def stop(self, reason):
        print('', flush=True)  # leaves the ^C on it's own line
        self.stopping = reason or 'unknown'

    async def connect_transport(self):
        addr = self.settings.sip_host, self.settings.sip_port
        connected = asyncio.Event()
        async with timeout(10):
            self.transport, _ = await self.loop.create_datagram_endpoint(
                lambda: SipProtocol(connected, self.datagram_callback),
                remote_addr=addr
            )
            await connected.wait()
        self.local_ip, _ = self.transport.get_extra_info('sockname')

    async def register(self, *, expires):
        common_headers = (
            f'From: <sip:{self.settings.sip_username}@{self.settings.sip_host}:{self.settings.sip_port}>',
            f'To: <sip:{self.settings.sip_username}@{self.settings.sip_host}:{self.settings.sip_port}>',
            f'Call-ID: {self.call_id}',
            f'Contact: <sip:{self.settings.sip_username}@{self.local_ip}>',
            f'Expires: {expires}',
            'Max-Forwards: 70',
            'User-Agent: TutorCruncher Mithra',
            'Content-Length: 0',
        )

        r1: Response = await self.request(
            f'REGISTER sip:{self.settings.sip_host}:{self.settings.sip_port} SIP/2.0',
            f'Via: SIP/2.0/UDP {self.local_ip}:5060;rport;branch={self.gen_branch()}',
            f'CSeq: {self.cseq} REGISTER',
            *common_headers,
        )
        if r1.status != 401:
            debug('unexpected response to first REGISTER', r1)
            logger.warning('unexpected response to first REGISTER %s != 401', r1.status, extra={
                'data': {'response': r1}
            })
            # honor "Retry-After"
            return int(r1.headers.get('Retry-After', self.ERROR_WAIT))

        auth = r1.headers['WWW-Authenticate']
        realm = REALM_REGEX.search(auth).groups()[0]
        nonce = NONCE_REGEX.search(auth).groups()[0]
        ha1 = md5digest(self.settings.sip_username, realm, self.settings.sip_password)
        ha2 = md5digest('REGISTER', self.settings.sip_uri)
        r2: Response = await self.request(
            f'REGISTER sip:{self.settings.sip_host}:{self.settings.sip_port} SIP/2.0',
            f'Via: SIP/2.0/UDP {self.local_ip}:5060;rport;branch={self.gen_branch()}',
            f'CSeq: {self.cseq} REGISTER',
            (
                f'Authorization: Digest username="{self.settings.sip_username}", realm="{realm}", nonce="{nonce}", '
                f'uri="{self.settings.sip_uri}", response="{md5digest(ha1, nonce, ha2)}", algorithm=MD5'
            ),
            *common_headers,
        )
        if expires == 0:
            logger.info('un-registered, response: %d', r2.status)
        elif r2.status != 200:
            debug('unexpected response to second REGISTER', r2)
            logger.warning('unexpected response to second REGISTER %d != 200', r2.status, extra={
                'data': {'response': r2}
            })
            # honor "Retry-After"
            return int(r2.headers.get('Retry-After', self.ERROR_WAIT))
        else:
            re_register = max(10, expires - 1)
            logger.info('successfully registered')
            self.sentinal_file.touch(exist_ok=True)
            return re_register

    def gen_branch(self):
        # "z9hG4bK" is a special value which branch is apparently supposed to start with
        return 'z9hG4bK' + secrets.token_hex()[:16]

    async def request(self, *req):
        request_data = '\r\n'.join(req) + '\r\n\r\n'
        async with self.request_lock:
            async with timeout(10):
                status, headers, response_data = await self._request(request_data)
        # debug(request_data, status, dict(headers))
        self.request_future = None
        return Response(status, headers, response_data, request_data)

    def _request(self, data: str):
        assert self.transport, 'no transport initialised'
        self.request_future = asyncio.Future()
        self.transport.sendto(data.encode())
        self.cseq += 1
        return self.request_future

    def datagram_callback(self, raw_data: bytes):
        headers, data = raw_data.split(b'\r\n\r\n', 1)
        status, headers = parse_headers(headers)
        if 'status_code' in status:
            self.process_response(status, headers, data)
        else:
            self.process_request(status, headers, data)

    def process_response(self, status, headers, data):
        if self.request_future:
            self.request_future.set_result((int(status['status_code']), headers, data))
        else:
            logger.warning('no request future for response: %s', status, extra={
                'data': {
                    'status': status,
                    'headers': headers,
                    'data': try_decode(data),
                }
            })

    def process_request(self, status, headers, data):
        method = status['method']
        if method == 'OPTIONS':
            # don't care
            pass
        elif method == 'INVITE':
            self.process_incoming_call(headers)
        else:
            logger.warning('unknown request: %s', method, extra={
                'data': {
                    'status': status,
                    'headers': headers,
                    'data': try_decode(data),
                }
            })

    def existing_call(self, from_header):
        # tag in from header remains the same for a given call but changes between calls:
        _existing_call = from_header in self.call_cache
        # very simple lru cache, if self.call_cache is 200 or longer cut to 100 including this call
        if len(self.call_cache) >= 200:
            self.call_cache = {k: 1 for k in list(self.call_cache.keys())[-99:]}
        self.call_cache[from_header] = 1
        return _existing_call

    def process_incoming_call(self, headers):
        from_header = headers['From']
        if self.existing_call(from_header):
            return
        m = NUMBER.search(from_header)
        if m:
            number = m.groups()[0]
        else:
            number = 'unknown'
            logger.warning('unable to find number in "%s"', from_header, extra={
                'data': {'headers': headers}
            })
        country = headers.get('X-Brand', None)
        logger.info(f'incoming call from %s%s', number, f' ({country})' if country else '')
        self.db.record_call(number, country)


async def setup(settings, loop):
    db = Database(settings, loop)
    await db.init()
    client = SipClient(settings, db, loop)
    await client.start()
    return client


def main():
    loop = asyncio.get_event_loop()
    settings = Settings()
    try:
        client: SipClient = loop.run_until_complete(setup(settings, loop))
        loop.run_until_complete(client.run_forever())
        client.task.result()
    finally:
        loop.close()
