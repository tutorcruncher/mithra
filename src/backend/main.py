import asyncio
import hashlib
import logging
import re
import secrets
from time import time

import asyncpg
from multidict import CIMultiDict

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


class EchoClientProtocol:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.transport = None
        self.auth_attempt = 0
        self.local_ip = None
        self.cseq = 1
        self.call_id = secrets.token_hex()[:10]
        self.last_invitation = 0

    def connection_made(self, transport):
        self.transport = transport
        self.local_ip, _ = transport.get_extra_info('sockname')
        logger.info('connection established')
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
Expires: 60
Content-Length: 0""")

    def datagram_received(self, data, addr):
        try:
            self.process_response(data, addr)
        except Exception as e:
            logger.error('error processing datagram %s: %s', type(e), e, extra={
                'data': {
                    'datagram': try_decode(data),
                    'addr': addr
                }
            })

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
Expires: 60
Content-Length: 0""")
        elif status_code == 200:
            logger.info('authenticated successfully')
            self.auth_attempt = 0
        elif status.get('method') == 'OPTIONS':
            # don't care
            pass
        elif status.get('method') == 'INVITE':
            n = time()
            if (n - self.last_invitation) > 1:
                self.process_invite(headers)
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

    def error_received(self, exc):
        logger.error('error received: %s', exc)

    def process_invite(self, headers):
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


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.conn = None

    async def init(self):
        self.conn = await asyncpg.create_pool(
            dsn=self.settings.pg_dsn,
            min_size=1,
            max_size=10,
        )


def main():
    loop = asyncio.get_event_loop()
    settings = Settings()
    addr = settings.sip_host, settings.sip_port
    connect = loop.create_datagram_endpoint(lambda: EchoClientProtocol(settings), remote_addr=addr)
    transport, protocol = loop.run_until_complete(connect)
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        transport.close()
        loop.close()
