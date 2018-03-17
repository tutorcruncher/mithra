import logging
from asyncio import CancelledError
from time import time

from aiohttp import WSMsgType
from aiohttp.web import Response
from aiohttp.web_ws import WebSocketResponse
from aiohttp_session import get_session

from .utils import JsonErrors, google_get_details, json_response, raw_json_response

logger = logging.getLogger('mithra.web')
TWO_WEEKS = 3600 * 24 * 7 * 2


async def index(request):
    return Response(text=request.app['index_html'], content_type='text/html')


async def signin_with_google(request):
    data = await request.json()
    try:
        details = await google_get_details(request.app['settings'], data['id_token'])
    except (KeyError, ValueError) as e:
        logger.exception('error parsing google sso token: %s', e)
        raise JsonErrors.HTTPBadRequest(text='invalid token')
    session = await get_session(request)
    session.update(
        expires=int(time()) + TWO_WEEKS,
        user=details,
    )
    return json_response(request, status='ok', details=details)


async def signout(request):
    session = await get_session(request)
    del session['expires']
    del session['user']
    return json_response(request, status='ok',)


calls_sql = """
SELECT array_to_json(array_agg(row_to_json(t)), TRUE)
FROM (
  SELECT c.id AS id, c.number AS number, c.country AS country, c.ts AS ts,
  p.name AS person_name, co.name AS company, co.has_support AS has_support
  FROM calls AS c
  LEFT JOIN people AS p ON c.person = p.id
  LEFT JOIN companies AS co ON p.company = co.id
  ORDER BY c.ts DESC
  LIMIT 100
) t;
"""


async def main_ws(request):
    ws = WebSocketResponse()

    session = await get_session(request)
    expires = session.get('expires', 0)
    await ws.prepare(request)
    if expires < time():
        await ws.close(code=4403)
        return ws

    json_str = await request.app['pg'].fetchval(calls_sql)
    await ws.send_str(json_str or '[]')
    request.app['ws_propagator'].add_ws(ws)
    try:
        async for msg in ws:
            logger.info('ws message:', msg)
            if msg.tp == WSMsgType.ERROR:
                logger.warning('ws connection closed with exception %s', ws.exception())
    except CancelledError:
        pass
    finally:
        request.app['ws_propagator'].remove_ws(ws)
    return ws


people_sql = """
SELECT array_to_json(array_agg(row_to_json(t)), TRUE)
FROM (
  SELECT p.id AS id, p.name AS name, p.last_seen AS last_seen,
  co.name AS company_name, co.id as company_id, co.has_support AS has_support
  FROM people AS p
  LEFT JOIN companies AS co ON p.company = co.id
  ORDER BY p.last_seen DESC
  LIMIT 100
) t;
"""


async def people(request):
    json_str = await request.app['pg'].fetchval(people_sql)
    # return as dict in case we want to add count etc. later
    return raw_json_response('{"items": %s}' % (json_str or '[]'))


companies_sql = """
SELECT array_to_json(array_agg(row_to_json(t)), TRUE)
FROM (
  SELECT id, name, login_url, created, has_support
  FROM companies
  ORDER BY created DESC
  LIMIT 100
) t;
"""


async def companies(request):
    json_str = await request.app['pg'].fetchval(companies_sql)
    # return as dict in case we want to add count etc. later
    return raw_json_response('{"items": %s}' % (json_str or '[]'))


call_details_sql = """
SELECT row_to_json(t)
FROM (
  SELECT c.id AS id, c.number AS number, c.country AS country, c.ts AS ts,
  p.id AS person_id, p.name AS person_name, p.last_seen AS person_last_seen, p.details AS person_details,
  co.id AS company_id, co.name AS company_name, co.has_support AS has_support
  FROM calls AS c
  LEFT JOIN people AS p ON c.person = p.id
  LEFT JOIN companies AS co ON p.company = co.id
  WHERE c.id=$1
) t;
"""


async def call_details(request):
    json_str = await request.app['pg'].fetchval(call_details_sql, int(request.match_info['id']))
    return raw_json_response(json_str or 'null')


person_details_sql = """
SELECT row_to_json(t)
FROM (
  SELECT p.id AS id, p.name AS name, p.last_seen AS last_seen, p.details AS details,
  co.id AS company_id, co.name AS company_name, co.has_support AS has_support, array_agg(pn.number) AS numbers
  FROM people p
  LEFT JOIN companies AS co ON p.company = co.id
  LEFT JOIN people_numbers AS pn ON p.id = pn.person
  WHERE p.id=$1
  GROUP BY p.id, co.id
) t;
"""


async def person_details(request):
    id = int(request.match_info['id'])
    json_str = await request.app['pg'].fetchval(person_details_sql, id)
    return raw_json_response(json_str or 'null')


company_details_sql = """
SELECT row_to_json(t)
FROM (
  SELECT * FROM companies WHERE id=$1
) t;
"""
company_people_sql = """
SELECT array_to_json(array_agg(row_to_json(t)), TRUE)
FROM (
  SELECT p.id AS id, p.name AS name, p.last_seen AS last_seen, array_agg(pn.number) AS numbers
  FROM people AS p
  LEFT JOIN companies AS co ON p.company = co.id
  LEFT JOIN people_numbers AS pn ON p.id = pn.person
  WHERE co.id=$1
  GROUP BY p.id, co.id
  ORDER BY p.last_seen DESC
  LIMIT 100
) t;
"""


async def company_details(request):
    co_id = int(request.match_info['id'])
    json_str = await request.app['pg'].fetchval(company_details_sql, co_id)
    if json_str:
        people_json_str = await request.app['pg'].fetchval(company_people_sql, co_id)
        json_str = json_str[:-1] + ', "people": %s}' % (people_json_str or '[]')
    return raw_json_response(json_str or 'null')


people_search_sql = """
SELECT array_to_json(array_agg(row_to_json(t)), TRUE)
FROM (
  SELECT p.id AS id, p.name AS name, p.last_seen AS last_seen,
  co.name AS company_name, co.id as company_id,
  similarity(search, $1) similarity

  FROM people AS p
  LEFT JOIN people_numbers AS pn ON p.id = pn.person
  LEFT JOIN companies AS co ON p.company = co.id
  WHERE p.search ILIKE $2
  GROUP BY p.id, co.id
  ORDER BY similarity DESC, p.last_seen DESC
  LIMIT 10
) t;
"""


async def search(request):
    query = request.query.get('q')
    json_str = await request.app['pg'].fetchval(people_search_sql, query, f'%{query}%')
    return raw_json_response(json_str or 'null')
