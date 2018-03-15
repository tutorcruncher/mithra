import logging

from aiohttp import WSMsgType
from aiohttp.web import Response
from aiohttp.web_ws import WebSocketResponse

logger = logging.getLogger('mithra.web')


async def index(request):
    return Response(text=request.app['index_html'], content_type='text/html')


calls_sql = """
SELECT array_to_json(array_agg(row_to_json(t)), TRUE)
FROM (
  SELECT c.id AS id, c.number AS number, c.country AS country, c.ts AS ts,
  p.name AS person_name, c2.name AS company
  FROM calls AS c
  LEFT JOIN people p ON c.person = p.id
  LEFT JOIN companies c2 ON p.company = c2.id
  ORDER BY c.ts DESC
  LIMIT 100
) t;
"""


async def main_ws(request):
    ws = WebSocketResponse()

    # cookie = request.cookies.get(request.app['settings'].cookie_name, '')
    # try:
    #     token = request.app['session_fernet'].decrypt(cookie.encode())
    # except InvalidToken:
    #     await ws.prepare(request)
    #     await ws.close(code=4403)
    #     return ws
    session = 'anon'
    # logger.info('ws connection %s', session)
    await ws.prepare(request)
    json_str = await request.app['pg'].fetchval(calls_sql)
    await ws.send_str(json_str or '[]')
    request.app['background'].add_ws(ws)
    try:
        async for msg in ws:
            logger.info('ws message:', msg)
            if msg.tp == WSMsgType.ERROR:
                logger.warning('ws connection closed with exception %s', ws.exception())
    finally:
        # logger.info('ws disconnection %s', session)
        request.app['background'].remove_ws(ws)
    return ws
