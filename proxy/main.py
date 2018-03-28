#!/usr/bin/env python3.6
import asyncio
import os
import signal

SIP_HOST = os.getenv('APP_SIP_HOST')
SIP_PORT = os.getenv('APP_SIP_PORT')
REMOTE_ADDR = SIP_HOST, SIP_PORT

PROXY_HOST = '0.0.0.0'
PROXY_PORT = SIP_PORT
PROXY_ADDR = PROXY_HOST, PROXY_PORT


def print_data(direction, data):
    # print(f'{direction} {"=" * 78}\n{data.decode()}\n{"=" * 80}')
    print(f'{direction} ', data.decode().split('\n', 1)[0])


class RemoteDatagramProtocol:
    def __init__(self, proxy, addr, data):
        self.proxy = proxy
        self.addr = addr
        self.data = data
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        print_data('▲', self.data)
        self.transport.sendto(self.data)

    def datagram_received(self, data, _):
        print_data('▼', data)
        self.proxy.transport.sendto(data, self.addr)

    def connection_lost(self, exc):
        self.proxy.remotes.pop(self.addr)

    def error_received(self, exc):
        print(f'remote error received: {exc}')


class ProxyDatagramProtocol:
    def __init__(self):
        self.remotes = {}
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if addr in self.remotes:
            print_data('▲', data)
            self.remotes[addr].transport.sendto(data)
        else:
            loop = asyncio.get_event_loop()
            self.remotes[addr] = RemoteDatagramProtocol(self, addr, data)
            loop.create_task(
                loop.create_datagram_endpoint(lambda: self.remotes[addr], remote_addr=REMOTE_ADDR)
            )

    def error_received(self, exc):
        print(f'proxy error received: {exc}')

    def connection_lost(self, exc):
        print(f'proxy connection lost: {exc}')


def stop(reason):
    print('')  # leaves the ^C on it's own line
    raise KeyboardInterrupt(f'reason "{reason or "unknown"}"')


async def start_datagram_proxy():
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, stop, 'sigint')
    loop.add_signal_handler(signal.SIGTERM, stop, 'sigterm')
    return await loop.create_datagram_endpoint(lambda: ProxyDatagramProtocol(), local_addr=PROXY_ADDR)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    print(f'starting proxy {PROXY_ADDR} to {REMOTE_ADDR}')
    transport, _ = loop.run_until_complete(start_datagram_proxy())
    print('UPD proxy is running...')
    try:
        loop.run_forever()
    except KeyboardInterrupt as e:
        print(f'exiting:', e)
    print('UDP proxy closing...')
    transport.close()
    loop.close()
