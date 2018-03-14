import asyncio
import hashlib
import json
import logging
import re
import secrets
from time import time

import asyncpg
from multidict import CIMultiDict

from shared.db import lenient_conn
from shared.settings import PgSettings

logger = logging.getLogger('mithra.backend.main')

AUTH_METHOD = 'REGISTER'
BRANCH = secrets.token_hex()[:16].upper()


class Settings(PgSettings):
    sip_host: str
    sip_port: int = 5060
    sip_username: str
    sip_password: str

    @property
    def sip_uri(self):
        return f'sip:{self.sip_host}:{self.sip_password}'


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


def parse_digest(header):
    params = {}
    for arg in header[7:].split(','):
        k, v = arg.strip().split('=', 1)
        if '="' in arg:
            v = v[1:-1]
        params[k] = v
    return params


RESPONSE_DECODE = re.compile(r'SIP/2.0 (?P<status_code>[0-9]{3}) (?P<status_message>.+)')
REQUEST_DECODE = re.compile(r'(?P<method>[A-Za-z]+) (?P<to_uri>.+) SIP/2.0')
NUMBER = re.compile(r'sip:(\d+)@')


def parse_headers(raw_headers):
    headers = CIMultiDict()
    decoded_headers = raw_headers.decode().split('\r\n')
    for line in decoded_headers[1:]:
        k, v = line.split(': ', 1)
        if k in headers:
            o = headers.setdefault(k, [])
            if not isinstance(o, list):
                o = [o]
            o.append(v)
            headers[k] = o
        else:
            headers[k] = v

    for regex in (REQUEST_DECODE, RESPONSE_DECODE):
        m = regex.match(decoded_headers[0])
        if m:
            return m.groupdict(), headers
    raise RuntimeError('unable to decode response')


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
        async with self._pg.acquire() as conn:
            # TODO get other info
            await conn.execute('INSERT INTO calls (number, country) VALUES ($1, $2)', number, country)
            data = json.dumps({
                'number': number,
                'country': country,
            })
            await conn.execute("SELECT pg_notify('call', $1::text)", data)

    async def close(self):
        await asyncio.gather(self.tasks)
        await self._pg.close()


class SipProtocol:
    def __init__(self, sip_client):
        self.client = sip_client

    def connection_made(self, transport):
        logger.info('connection established')
        self.client.connection_made(transport)

    def datagram_received(self, data, addr):
        try:
            self.client.process_response(data, addr)
        except Exception as e:
            logger.error('error processing datagram %s: %s', type(e), e, extra={
                'data': {
                    'datagram': try_decode(data),
                    'addr': addr
                }
            })

    def error_received(self, exc):
        logger.error('error received: %s', exc)


class SipClient:
    def __init__(self, settings: Settings, db: Database, loop):
        self.settings = settings
        self.db = db
        self.loop = loop
        self.transport = None
        self.auth_attempt = 0
        self.authenticated = False
        self.local_ip = None
        self.cseq = 1
        self.call_id = secrets.token_hex()[:10]
        self.last_invitation = 0

    def protocol_factory(self):
        return SipProtocol(self)

    def connection_made(self, transport):
        self.transport = transport
        self.local_ip, _ = transport.get_extra_info('sockname')
        self.authenticate()

    def authenticate(self):
        self.auth_attempt = 0
        self.authenticated = False
        self.send(f"""\
{AUTH_METHOD} sip:{self.settings.sip_host}:{self.settings.sip_port} SIP/2.0
Via: SIP/2.0/UDP {self.local_ip}:5060;rport;branch={BRANCH}
From: <sip:{self.settings.sip_username}@{self.settings.sip_host}:{self.settings.sip_port}>;tag=1269824498
To: <sip:{self.settings.sip_username}@{self.settings.sip_host}:{self.settings.sip_port}>
Call-ID: {self.call_id}
CSeq: {self.cseq} {AUTH_METHOD}
Contact: <sip:{self.settings.sip_username}@{self.local_ip};line=9ad550fb9d87b0f>
Max-Forwards: 70
User-Agent: TutorCruncher Address Book
Expires: 3600
Content-Length: 0""")

    def process_response(self, raw_data: bytes, addr):
        if raw_data.startswith(b'\x00'):
            # ping from server, ignore
            return
        headers, data = raw_data.split(b'\r\n\r\n', 1)
        status, headers = parse_headers(headers)
        status_code = int(status.get('status_code', 0))
        if status_code == 401:
            if self.auth_attempt > 1:
                logger.error('repeated auth attempt')
                return
            self.auth_attempt += 1
            auth = headers['WWW-Authenticate']
            params = parse_digest(auth)
            realm, nonce = params['realm'], params['nonce']
            ha1 = md5digest(self.settings.sip_username, realm, self.settings.sip_password)
            ha2 = md5digest(AUTH_METHOD, self.settings.sip_uri)
            self.send(f"""\
{AUTH_METHOD} sip:{self.settings.sip_host}:{self.settings.sip_port} SIP/2.0
Via: SIP/2.0/UDP {self.local_ip}:5060;rport;branch={BRANCH}
From: <sip:{self.settings.sip_username}@{self.settings.sip_host}:{self.settings.sip_port}>;tag=1269824498
To: <sip:{self.settings.sip_username}@{self.settings.sip_host}:{self.settings.sip_port}>
Call-ID: {self.call_id}
CSeq: {self.cseq} {AUTH_METHOD}
Contact: <sip:{self.settings.sip_username}@{self.local_ip};line=9ad550fb9d87b0f>
Authorization: Digest username="{self.settings.sip_username}", realm="{realm}", nonce="{nonce}", \
uri="{self.settings.sip_uri}", response="{md5digest(ha1, nonce, ha2)}", algorithm=MD5
Max-Forwards: 70
User-Agent: TutorCruncher Address Book
Expires: 3600
Content-Length: 0""")
        elif not self.authenticated and status_code == 503:
            logger.warning('503 while authenticating, retying in 8 seconds...', extra={
                'data': {
                    'status': status,
                    'headers': headers,
                    'data': try_decode(data),
                }
            })
            self.loop.call_later(8, self.authenticate)
        elif not self.authenticated and status_code == 200:
            logger.info('authenticated successfully')
            self.authenticated = True
        elif status.get('method') == 'OPTIONS':
            # don't care
            pass
        elif status.get('method') == 'INVITE':
            n = time()
            if (n - self.last_invitation) > 1:
                self.process_invite_request(headers)
            self.last_invitation = n
        else:
            logger.warning('unknown datagram: %s', status, extra={
                'data': {
                    'status': status,
                    'headers': headers,
                    'data': try_decode(data),
                }
            })

    def send(self, data):
        data = (data.strip('\n ') + '\n\n').replace('\n', '\r\n').encode()
        self.transport.sendto(data)
        self.cseq += 1

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

    def close(self):
        self.transport.close()
        self.loop.close()


async def setup(settings, loop):
    addr = settings.sip_host, settings.sip_port
    db = Database(settings, loop)
    await db.init()
    client = SipClient(settings, db, loop)
    await loop.create_datagram_endpoint(client.protocol_factory, remote_addr=addr)
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
        client.close()
