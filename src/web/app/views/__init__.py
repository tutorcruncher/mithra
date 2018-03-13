from aiohttp import web_exceptions
from aiohttp.web import Response


async def index(request):
    return Response(text=request.app['index_html'], content_type='text/html')


ROBOTS = """\
User-agent: *
Allow: /
"""


async def robots_txt(request):
    return Response(text=ROBOTS, content_type='text/plain')


async def favicon(request):
    raise web_exceptions.HTTPMovedPermanently('https://secure.tutorcruncher.com/favicon.ico')
