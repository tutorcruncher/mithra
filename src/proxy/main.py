#!/usr/bin/env python3.6
import asyncio
import logging
import signal
from enum import IntEnum

import asyncpg

from shared.db import lenient_conn
from shared.settings import PgSettings

try:
    from devtools import debug
except ImportError:
    def debug(*args, **kwargs):
        pass

logger = logging.getLogger('mithra.proxy.main')


class Settings(PgSettings):
    sip_host: str
    sip_port: int = 5060
    proxy_host: str = '0.0.0.0'

    cache_dir: str = '/tmp/mithra'
    sentinel_file: str = 'sentinel.txt'

    @property
    def sip_addr(self):
        return self.sip_host, self.sip_port

    @property
    def proxy_addr(self):
        return self.proxy_host, self.sip_port


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


class Directions(IntEnum):
    inbound = 1
    outbound = 2


async def record(direction: Directions, data: bytes, db: Database):
    # print(f'{direction} {"=" * 78}\n{data.decode()}\n{"=" * 80}')
    print(f'{"▼" if direction == Directions.inbound else "▲"} ', data.decode().split('\n', 1)[0])


class RemoteDatagramProtocol:
    def __init__(self, proxy, addr, data):
        self.proxy = proxy
        self.addr = addr
        self.init_data = data
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        self.proxy.record(Directions.outbound, self.init_data)
        self.transport.sendto(self.init_data)
        self.init_data = None

    def datagram_received(self, data, _):
        self.proxy.record(Directions.inbound, data)
        self.proxy.transport.sendto(data, self.addr)

    def connection_lost(self, exc):
        if exc:
            logger.warning('remote connection lost: %s', exc)
        else:
            logger.debug('remote connection lost')
        self.proxy.remotes.pop(self.addr)

    def error_received(self, exc):
        logger.error('remote error received: %s', exc)


class ProxyDatagramProtocol:
    def __init__(self, settings: Settings, db: Database, loop):
        self.settings = settings
        self.db = db
        self.loop = loop
        self.remotes = {}
        self.transport = None

    def record(self, direction: Directions, data: bytes):
        self.loop.create_task(record(direction, data, self.db))

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if addr in self.remotes:
            self.record(Directions.outbound, data)
            self.remotes[addr].transport.sendto(data)
        else:
            self.remotes[addr] = RemoteDatagramProtocol(self, addr, data)
            self.loop.create_task(
                self.loop.create_datagram_endpoint(lambda: self.remotes[addr], remote_addr=self.settings.sip_addr)
            )

    def connection_lost(self, exc):
        if exc:
            logger.warning('proxy connection lost: %s', exc)
        else:
            logger.debug('proxy connection lost')

    def error_received(self, exc):
        logger.error('proxy error received: %s', exc)


class GracefulShutdown(RuntimeError):
    pass


class Proxy:
    def __init__(self, settings: Settings, loop):
        self.settings = settings
        self.loop = loop
        self.db = Database(settings, loop)
        self.stopping = None
        self.task = None

    async def start(self):
        await self.db.init()
        self.loop.add_signal_handler(signal.SIGINT, self.stop, 'sigint')
        self.loop.add_signal_handler(signal.SIGTERM, self.stop, 'sigterm')
        self.task = self.loop.create_task(self.main_task())

    async def main_task(self):
        proto = ProxyDatagramProtocol(self.settings, self.db, self.loop)
        transport, _ = await self.loop.create_datagram_endpoint(lambda: proto, local_addr=self.settings.proxy_addr)
        try:

            while True:
                await asyncio.sleep(600)
                # save sentinel

        except GracefulShutdown:
            pass
        finally:
            logger.info('stopping reason: "%s"...', self.stopping)
            await self.db.complete_tasks()
            if transport:
                transport.close()
            await self.db.close()

    async def run_forever(self):
        await self.task

    def stop(self, reason):
        print('')  # leaves the ^C on it's own line
        self.stopping = reason or 'unknown'
        raise GracefulShutdown()


def main():
    loop = asyncio.get_event_loop()
    settings = Settings()
    try:
        proxy = Proxy(settings, loop)
        loop.run_until_complete(proxy.run_forever())
        proxy.task.result()
    finally:
        loop.close()
