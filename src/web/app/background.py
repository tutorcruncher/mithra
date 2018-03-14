import asyncio
import logging

logger = logging.getLogger('mithra.web.background')


class Background:
    def __init__(self, app):
        self.app = app
        self.running = True
        loop = asyncio.get_event_loop()
        self.task = loop.create_task(self._run())
        self.websockets = set()

    def add_ws(self, ws):
        self.websockets.add(ws)

    def remove_ws(self, ws):
        try:
            self.websockets.remove(ws)
        except KeyError:
            pass

    async def close(self):
        logger.info('closing web background task')
        self.running = False
        await self.task
        self.task.result()

    async def _run(self):
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
