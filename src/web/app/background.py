import asyncio
import logging

from .settings import Settings

logger = logging.getLogger('mithra.web.background')


class _Worker:
    def __init__(self, app):
        self.app = app
        self.settings: Settings = app['settings']
        self.running = True
        loop = asyncio.get_event_loop()
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
        pg = self.app['pg']
        channel = 'call'
        async with pg.acquire() as conn:
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


class Downloader(_Worker):
    FREQ = 3600
    ERROR_FREQ = 60

    async def download(self):
        logger.info('running intercom download')

    async def run(self):
        while True:
            try:
                await self.download()
            except Exception as e:
                logger.exception('Error running intercom downloader: %s', e)
                wait = self.ERROR_FREQ
            else:
                wait = self.FREQ

            for i in range(wait):
                await asyncio.sleep(1)
                if not self.running:
                    return
