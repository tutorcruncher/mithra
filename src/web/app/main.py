import os
import re
from html import escape

import asyncpg
from aiohttp import web

from shared.db import prepare_database

from .settings import THIS_DIR, Settings
from .views import favicon, index, robots_txt


async def startup(app: web.Application):
    settings: Settings = app['settings']
    await prepare_database(settings, False)
    app.update(
        pg=await asyncpg.create_pool(dsn=settings.pg_dsn)
    )


async def cleanup(app: web.Application):
    await app['pg'].close()


def setup_routes(app):
    app.router.add_get('/', index, name='index')
    app.router.add_get('/robots.txt', robots_txt, name='robots-txt')
    app.router.add_get('/favicon.ico', favicon, name='favicon')


def create_app(*, settings: Settings=None):
    app = web.Application()
    settings = settings or Settings()
    app['settings'] = settings

    ctx = dict(
        COMMIT=os.getenv('COMMIT', '-'),
        RELEASE_DATE=os.getenv('RELEASE_DATE', '-'),
        SERVER_NAME=os.getenv('SERVER_NAME', '-'),
    )
    index_html = (THIS_DIR / 'index.html').read_text()
    for key, value in ctx.items():
        index_html = re.sub(r'\{\{ ?%s ?\}\}' % key, escape(value), index_html)
    app['index_html'] = index_html
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)

    setup_routes(app)
    return app
