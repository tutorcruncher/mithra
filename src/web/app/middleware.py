import logging
from time import time

from aiohttp.web_exceptions import HTTPException, HTTPInternalServerError
from aiohttp.web_middlewares import middleware
from aiohttp.web_urldispatcher import SystemRoute
from aiohttp_session import get_session

from .utils import JsonErrors

request_logger = logging.getLogger('mithra.web.middleware')
IP_HEADER = 'X-Forwarded-For'


def get_ip(request):
    ips = request.headers.get(IP_HEADER)
    if ips:
        return ips.split(',', 1)[0].strip(' ')
    else:
        return request.remote


async def log_extra(request, response=None):
    return {'data': dict(
        request_url=str(request.rel_url),
        request_ip=get_ip(request),
        request_method=request.method,
        request_host=request.host,
        request_headers=dict(request.headers),
        request_text=await request.text(),
        response_status=getattr(response, 'status', None),
        response_headers=dict(getattr(response, 'headers', {})),
        response_text=getattr(response, 'text', None)
    )}


async def log_warning(request, response):
    ip, ua = get_ip(request), request.headers.get('User-Agent')
    request_logger.warning('%s %d from %s ua: "%s"', request.rel_url, response.status, ip, ua, extra={
        'fingerprint': [request.rel_url, str(response.status)],
        'data': await log_extra(request, response)
    })


@middleware
async def error_middleware(request, handler):
    try:
        http_exception = getattr(request.match_info, 'http_exception', None)
        if http_exception:
            raise http_exception
        else:
            r = await handler(request)
    except HTTPException as e:
        if e.status > 310:
            await log_warning(request, e)
        raise
    except BaseException as e:
        request_logger.exception('%s: %s', e.__class__.__name__, e, extra={
            'fingerprint': [e.__class__.__name__, str(e)],
            'data': await log_extra(request)
        })
        raise HTTPInternalServerError()
    else:
        if r.status > 310:
            await log_warning(request, r)
    return r

PUBLIC_VIEWS = {
    'index',
    'signin',
    'ws',  # authentication is done by ws so it can return a websocket code
    'search',  # TODO remove
}


@middleware
async def auth_middleware(request, handler):
    if isinstance(request.match_info.route, SystemRoute):
        # eg. 404
        return await handler(request)
    route_name = request.match_info.route.name
    route_name = route_name and route_name.replace('-head', '')
    if route_name not in PUBLIC_VIEWS:
        session = await get_session(request)
        if not session:
            raise JsonErrors.HTTPForbidden(status='not authenticated')

        expires = session.get('expires', 0)
        if expires < time():
            raise JsonErrors.HTTPForbidden(status=f'session expired: {expires}')
    return await handler(request)
