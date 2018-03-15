import base64
import os
import re
from html import escape

import asyncpg
from aiohttp import web

from aiohttp_session import session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from shared.db import prepare_database
from .background import Background
from .middleware import error_middleware, auth_middleware
from .settings import THIS_DIR, Settings
from .views import (
    call_details,
    companies,
    company_details,
    index,
    main_ws,
    people,
    person_details,
    signin_with_google,
    signout,
)


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
    app.router.add_get('/api/people/', people, name='people')
    app.router.add_get('/api/companies/', companies, name='companies')

    app.router.add_get('/api/calls/{id:\d+}/', call_details, name='call-details')
    app.router.add_get('/api/people/{id:\d+}/', person_details, name='person-details')
    app.router.add_get('/api/companies/{id:\d+}/', company_details, name='company-details')

    app.router.add_post('/api/signin/', signin_with_google, name='signin')
    app.router.add_post('/api/signout/', signout, name='signout')


def create_app(*, settings: Settings=None):
    settings = settings or Settings()

    secret_key = base64.urlsafe_b64decode(settings.auth_key)
    app = web.Application(middlewares=(
        error_middleware,
        session_middleware(EncryptedCookieStorage(secret_key, cookie_name='mithra')),
        auth_middleware,
    ))
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
