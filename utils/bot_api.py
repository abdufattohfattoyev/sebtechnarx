# utils/bot_api.py — Bot HTTP API serveri
# Aiogram bilan parallel ishlaydigan aiohttp web server.
# Django shu yerga so'rov yuboradi.

import asyncio
import logging
import threading

logger = logging.getLogger(__name__)


async def _handle_check_phones(request):
    """
    POST /api/check-phones
    Body: { "phones": ["+998901234567", ...], "token": "BOT_TOKEN" }
    Response: { "results": { "+998901234567": 123456789, ... } }
    """
    from data.config import BOT_TOKEN
    from utils.db_api.user_database import get_user_conn
    import psycopg2.extras
    from aiohttp import web

    try:
        data = await request.json()
    except Exception:
        return web.json_response({'error': 'JSON xato'}, status=400)

    if data.get('token') != BOT_TOKEN:
        return web.json_response({'error': 'Ruxsat yoq'}, status=403)

    phones = data.get('phones', [])
    if not phones:
        return web.json_response({'results': {}})

    results = {p: None for p in phones}

    try:
        conn   = get_user_conn()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT phone_number, telegram_id FROM users WHERE phone_number IS NOT NULL"
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Oxirgi 9 raqam bo'yicha indeks
        lookup = {}
        for row in rows:
            if row['phone_number']:
                key = row['phone_number'].lstrip('+').lstrip('0')[-9:]
                lookup[key] = row['telegram_id']

        for phone in phones:
            key = str(phone).lstrip('+').lstrip('0')[-9:]
            results[phone] = lookup.get(key)

    except Exception as e:
        logger.error(f"[bot_api] check-phones xato: {e}")
        return web.json_response({'error': str(e)}, status=500)

    logger.info(f"[bot_api] check-phones: {len(phones)} ta telefon tekshirildi")
    return web.json_response({'results': results})


def _run_server(port: int):
    """Alohida eventloop bilan aiohttp web server"""
    from aiohttp import web

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = web.Application()
    app.router.add_post('/api/check-phones', _handle_check_phones)

    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, '0.0.0.0', port)
    loop.run_until_complete(site.start())
    logger.info(f"✅ Bot API server ishga tushdi: http://0.0.0.0:{port}")
    loop.run_forever()


def start_bot_api(port: int = 3002):
    """Botni ishga tushirganda chaqiriladi — threadda API serverni yoqadi"""
    t = threading.Thread(target=_run_server, args=(port,), daemon=True, name="BotAPIServer")
    t.start()
    return t
