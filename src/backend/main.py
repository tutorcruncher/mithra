import asyncio
import hashlib
import logging
import re
import secrets
from time import time
from typing import NamedTuple

import asyncpg
from multidict import CIMultiDict

from shared.db import lenient_conn
from shared.settings import PgSettings

logger = logging.getLogger('mithra.backend.main')


class Settings(PgSettings):
    sip_host: str
    sip_port: int = 5060
    sip_username: str
    sip_password: str

    @property
    def sip_uri(self):
        return f'sip:{self.sip_host}:{self.sip_password}'


REALM_REGEX = re.compile('realm="(.+?)"')
NONCE_REGEX = re.compile('nonce="(.+?)"')
RESPONSE_DECODE = re.compile(r'SIP/2.0 (?P<status_code>[0-9]{3}) (?P<status_message>.+)')
REQUEST_DECODE = re.compile(r'(?P<method>[A-Za-z]+) (?P<to_uri>.+) SIP/2.0')
FIND_BRANCH = re.compile(r'branch=(.+?);')
NUMBER = re.compile(r'sip:(\d+)@')


class Response(NamedTuple):
    status: int
    headers: CIMultiDict
    response_data: bytes
    request_data: str


def parse_headers(raw_headers):
    headers = CIMultiDict()
    decoded_headers = raw_headers.decode().split('\r\n')
    for line in decoded_headers[1:]:
        k, v = line.split(': ', 1)
        headers.add(k, v)

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
        self._pg = await asyncpg.create_pool(dsn=self.settings.pg_dsn)

    def record_call(self, number, country):
        self.tasks.append(self._loop.create_task(self._record_call(number, country)))

    async def _record_call(self, number, country):
        number = number.replace(' ', '').upper()
        await self._pg.execute('INSERT INTO calls (number, country) VALUES ($1, $2)', number, country)

    async def close(self):
        await asyncio.gather(*self.tasks)
        await self._pg.close()


class SipProtocol:
    def __init__(self, sip_client):
        self.client = sip_client

    def connection_made(self, transport):
        logger.info('connection established')
        self.client.connection_made(transport)

    def datagram_received(self, data, addr):
        try:
            self.client.process_datagram(data, addr)
        except Exception as e:
            logger.error('error processing datagram %s: %s', type(e), e, extra={
                'data': {
                    'datagram': try_decode(data),
                    'addr': addr
                }
            })

    def error_received(self, exc):
        logger.error('error received: %s', exc)

    def connection_lost(self, exc):
        logger.debug('connection lost: %s', exc)


class SipClient:
    def __init__(self, settings: Settings, db: Database, loop):
        self.settings = settings
        self.db = db
        self.loop = loop
        self.transport = None
        self.local_ip = None
        self.cseq = 1
        self.call_id = secrets.token_hex()[:10]
        self.last_invitation = 0
        self.connected = asyncio.Event()
        self.request_lock = asyncio.Lock()
        self.request_future = None

    async def init(self):
        addr = self.settings.sip_host, self.settings.sip_port
        await self.loop.create_datagram_endpoint(self.protocol_factory, remote_addr=addr)
        await self.connected.wait()
        await self.register()

    async def register(self, expires=300):
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
            f'Via: SIP/2.0/UDP {self.local_ip}:5060;rport;branch=__branch__',
            f'CSeq: {self.cseq} REGISTER',
            *common_headers,
        )
        if r1.status != 401:
            logger.warning('unexpected response to first REGISTER %s != 401', r1.status, extra={
                'data': {'response': r1}
            })
            return

        auth = r1.headers['WWW-Authenticate']
        realm = REALM_REGEX.search(auth).groups()[0]
        nonce = NONCE_REGEX.search(auth).groups()[0]
        ha1 = md5digest(self.settings.sip_username, realm, self.settings.sip_password)
        ha2 = md5digest('REGISTER', self.settings.sip_uri)
        r2: Response = await self.request(
            f'REGISTER sip:{self.settings.sip_host}:{self.settings.sip_port} SIP/2.0',
            f'Via: SIP/2.0/UDP {self.local_ip}:5060;rport;branch=__branch__',
            f'CSeq: {self.cseq} REGISTER',
            (
                f'Authorization: Digest username="{self.settings.sip_username}", realm="{realm}", nonce="{nonce}", '
                f'uri="{self.settings.sip_uri}", response="{md5digest(ha1, nonce, ha2)}", algorithm=MD5'
            ),
            *common_headers,
        )
        if r2.status != 200:
            logger.warning('unexpected response to second REGISTER %s != 200', r2.status, extra={
                'data': {'response': r2}
            })
            # TODO look at headers and decide how long to wait to retry
        elif expires == 0:
            logger.info('successfully un-registered')
        else:
            re_register = max(10, expires - 10)
            logger.info('successfully registered, re-registering in %d seconds', re_register)
            self.loop.call_later(re_register, lambda: self.loop.create_task(self.register(expires)))

    def protocol_factory(self):
        return SipProtocol(self)

    def connection_made(self, transport):
        self.transport = transport
        self.local_ip, _ = transport.get_extra_info('sockname')
        self.connected.set()

    async def request(self, *req):
        branch = 'z9hG4bK' + secrets.token_hex()[:16].upper()
        request_data = '\r\n'.join(req).replace('__branch__', branch) + '\r\n\r\n'
        async with self.request_lock:
            status, headers, response_data = await self._request(request_data)
        # debug(request_data, status, dict(headers))
        self.request_future = None
        return Response(status, headers, response_data, request_data)

    def _request(self, data: str):
        self.transport.sendto(data.encode())
        self.cseq += 1
        self.request_future = asyncio.Future()
        return self.request_future

    def process_datagram(self, raw_data: bytes, addr):
        if raw_data.startswith(b'\x00'):
            # ping from server, ignore
            return
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
            n = time()
            if (n - self.last_invitation) > 1:
                self.process_invite_request(headers)
            self.last_invitation = n
        else:
            logger.warning('unknown request: %s', method, extra={
                'data': {
                    'status': status,
                    'headers': headers,
                    'data': try_decode(data),
                }
            })

    def process_invite_request(self, headers):
        from_header = headers['From']
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

    async def close(self):
        logger.info('un-registering...')
        await self.register(expires=0)
        self.transport.close()
        await self.db.close()


async def setup(settings, loop):
    db = Database(settings, loop)
    await db.init()
    client = SipClient(settings, db, loop)
    await client.init()
    return client


def main():
    loop = asyncio.get_event_loop()
    settings = Settings()
    client = loop.run_until_complete(setup(settings, loop))
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        print('')
        loop.run_until_complete(client.close())
        loop.close()
