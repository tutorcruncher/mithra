import asyncio
import os

from shared.db import lenient_conn, prepare_database

from .settings import Settings

patches = []


def reset_database(settings: Settings):
    if not (os.getenv('CONFIRM_DATABASE_RESET') == 'confirm' or input('Confirm database reset? [yN] ') == 'y'):
        print('cancelling')
    else:
        print('resetting database...')
        loop = asyncio.get_event_loop()
        loop.run_until_complete(prepare_database(settings, True))
        print('done.')


def patch(func):
    patches.append(func)
    return func


def run_patch(settings: Settings, live, patch_name):
    if patch_name is None:
        print('available patches:\n{}'.format(
            '\n'.join('  {}: {}'.format(p.__name__, p.__doc__.strip('\n ')) for p in patches)
        ))
        return
    patch_lookup = {p.__name__: p for p in patches}
    try:
        patch_func = patch_lookup[patch_name]
    except KeyError as e:
        raise RuntimeError(f'patch "{patch_name}" not found in patches: {[p.__name__ for p in patches]}') from e

    print(f'running patch {patch_name} live {live}')
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_run_patch(settings, live, patch_func))


async def _run_patch(settings, live, patch_func):
    conn = await lenient_conn(settings)
    tr = conn.transaction()
    await tr.start()
    print('=' * 40)
    try:
        await patch_func(conn)
    except BaseException as e:
        print('=' * 40)
        await tr.rollback()
        raise RuntimeError('error running patch, rolling back') from e
    else:
        print('=' * 40)
        if live:
            print('live, committed patch')
            await tr.commit()
        else:
            print('not live, rolling back')
            await tr.rollback()
    finally:
        await conn.close()


@patch
async def print_tables(conn):
    """
    print names of all tables
    """
    # TODO unique, indexes, references
    result = await conn.fetch("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public'")
    type_lookup = {
        'int4': 'INT',
        'float8': 'FLOAT',
    }
    for table_name, *_ in result:
        r = await conn.fetch('SELECT column_name, udt_name, character_maximum_length, is_nullable, column_default '
                             'FROM information_schema.columns WHERE table_name=$1', table_name)
        fields = []
        for name, col_type, max_chars, nullable, dft in r:
            col_type = type_lookup.get(col_type, col_type.upper())
            field = [name]
            if col_type == 'VARCHAR':
                field.append(f'{col_type}({max_chars})')
            else:
                field.append(col_type)
            if nullable == 'NO':
                field.append('NOT NULL')
            if dft:
                field.append(f'DEFAULT {dft}')
            fields.append(' '.join(field))
        print('{} (\n  {}\n)\n'.format(table_name, '\n  '.join(fields)))
