import base64
import os
import re
from html import escape

import asyncpg
from aiohttp import web

from aiohttp_session import setup
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from shared.db import prepare_database
from .background import Background
from .middleware import middleware
from .settings import THIS_DIR, Settings
from .views import index, main_ws, signin_with_google


async def startup(app: web.Application):
    settings: Settings = app['settings']
    await prepare_database(settings, False)
    app.update(
        pg=await asyncpg.create_pool(dsn=settings.pg_dsn),
        background=Background(app),
    )


async def cleanup(app: web.Application):
    await app['background'].close()
    await app['pg'].close()


def setup_routes(app):
    app.router.add_get('/api/', index, name='index')
    app.router.add_get('/api/ws/', main_ws, name='ws')
    app.router.add_post('/api/signin/', signin_with_google, name='signin')


def create_app(*, settings: Settings=None):
    app = web.Application(middlewares=middleware)
    settings = settings or Settings()
    app['settings'] = settings

    secret_key = base64.urlsafe_b64decode(settings.auth_key)
    setup(app, EncryptedCookieStorage(secret_key, cookie_name='mithra', domain='localhost:3000'))

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
