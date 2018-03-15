import logging

from aiohttp.web_exceptions import HTTPException, HTTPInternalServerError
from aiohttp.web_middlewares import middleware
from aiohttp.web_urldispatcher import SystemRoute
from aiohttp_session import get_session

from .utils import JsonErrors

request_logger = logging.getLogger('mithra.web.middleware')


async def log_extra(request, response=None):
    return {'data': dict(
        request_url=str(request.rel_url),
        request_method=request.method,
        request_host=request.host,
        request_headers=dict(request.headers),
        request_text=await request.text(),
        response_status=getattr(response, 'status', None),
        response_headers=dict(getattr(response, 'headers', {})),
        response_text=getattr(response, 'text', None)
    )}


async def log_warning(request, response):
    request_logger.warning('%s %d', request.rel_url, response.status, extra={
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
        debug(session)
        # if company:
        #     await authenticate(request, company.private_key.encode())
        # else:
        #     await authenticate(request)
    return await handler(request)


middleware = (
    error_middleware,
    auth_middleware
)
