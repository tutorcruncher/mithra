import logging
from time import time

from aiohttp import WSMsgType
from aiohttp.web import Response
from aiohttp.web_ws import WebSocketResponse
from aiohttp_session import get_session

from .utils import JsonErrors, json_response, google_get_details

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
TWO_WEEKS = 3600 * 24 * 7 * 2


async def signin_with_google(request):
    data = await request.json()
    try:
        details = await google_get_details(request.app['settings'], data['id_token'])
    except (KeyError, ValueError) as e:
        logger.exception('error parsing google sso token: %s', e)
        raise JsonErrors.HTTPBadRequest(text='invalid token')
    session = await get_session(request)
    debug(session)
    session['expires'] = int(time()) + TWO_WEEKS
    session['user'] = details
    return json_response(request, status='ok', details=details)


async def main_ws(request):
    ws = WebSocketResponse()

    session = await get_session(request)
    debug(session)
    expires = session.get('expires', 0)
    await ws.prepare(request)
    if expires < time():
        await ws.close(code=4403)
        return ws

    json_str = await request.app['pg'].fetchval(calls_sql)
    await ws.send_str(json_str or '[]')
    request.app['background'].add_ws(ws)
    try:
        async for msg in ws:
            logger.info('ws message:', msg)
            if msg.tp == WSMsgType.ERROR:
                logger.warning('ws connection closed with exception %s', ws.exception())
    finally:
        request.app['background'].remove_ws(ws)
    return ws
