import argparse
import asyncio
import json
import os
import time

from aiohttp import web
import daemon

from db import connect, Database
from log import log, add_file_handler, set_log_level, shutdown_logging
from twitter_session import TwitterSession

LOG_FILE = None
DEBUG_FILE = None
DB: Database

routes = web.RouteTableDef()

def log_session_info(sessions):
    text = ""
    for session in sessions:
        text += "\n%6d %5d %9d %5d" % (int(session.locked), session.limit, session.remaining, session.reset - int(time.time()))
    return text

@routes.get('/.stats')
async def stats(request):
    text = "--- GUEST SESSIONS ---\n\nLocked Limit Remaining Reset"
    text += log_session_info(TwitterSession.guest_sessions)
    text += "\n\n\n--- ACCOUNTS ---\n\nLocked Limit Remaining Reset"
    text += log_session_info(TwitterSession.account_sessions)
    return web.Response(text=text)

@routes.get('/.unlocked/{screen_name}')
async def unlocked(request):
    screen_name = request.match_info['screen_name']
    text = "Not unlocked"
    for session in TwitterSession.account_sessions:
        if session.username.lower() != screen_name.lower():
            continue
        session.locked = False
        text = "Unlocked"
    return web.Response(text=text)


@routes.get('/{screen_name}')
async def api(request):
    screen_name = request.match_info['screen_name']
    session = TwitterSession.guest_sessions[TwitterSession.test_index % len(TwitterSession.guest_sessions)]
    TwitterSession.test_index += 1
    result = await session.test(screen_name)
    DB.write_result(result)
    log.debug('\n %s', json.dumps(result))
    if args.cors_allow is not None:
        return web.json_response(result, headers={"Access-Control-Allow-Origin": args.cors_allow})

    return web.json_response(result)

async def login_accounts(accounts, cookie_dir=None):
    if cookie_dir is not None and not os.path.isdir(cookie_dir):
        os.mkdir(cookie_dir, 0o700)
    coroutines = []
    for acc in accounts:
        session = TwitterSession()
        coroutines.append(session.login(**acc, cookie_dir=cookie_dir))
        TwitterSession.account_sessions.append(session)
    await asyncio.gather(*coroutines)

async def login_guests():
    for _ in range(0, guest_session_pool_size):
        session = TwitterSession()
        TwitterSession.guest_sessions.append(session)
    await asyncio.gather(*[s.login() for s in TwitterSession.guest_sessions])
    log.info("%d guest sessions created", len(TwitterSession.guest_sessions))

def ensure_dir(path):
    if os.path.isdir(path) is False:
        log.info('Creating directory %s', path)
        os.mkdir(path)

parser = argparse.ArgumentParser(description='Twitter Shadowban Tester')
parser.add_argument('--account-file', type=str, default='.htaccounts', help='json file with reference account credentials')
parser.add_argument('--cookie-dir', type=str, default=None, help='directory for session cookies')
parser.add_argument('--log', type=str, default='./logs/backend.log', help='file to write logs to (default: ./logs/backend.log)')
parser.add_argument('--daemon', action='store_true', help='run in background')
parser.add_argument('--debug', action='store_true', help='show debug log messages')
parser.add_argument('--port', type=int, default=8080, help='port which to listen on (default: 8080)')
parser.add_argument('--host', type=str, default='127.0.0.1', help='hostname/ip which to listen on (default:127.0.0.1)')
parser.add_argument('--mongo-host', type=str, default='localhost', help='hostname or IP of mongoDB service to connect to (default: localhost)')
parser.add_argument('--mongo-port', type=int, default=27017, help='port of mongoDB service to connect to (default: 27017)')
parser.add_argument('--mongo-DB', type=str, default='tester', help='name of mongo database to use (default: tester)')
parser.add_argument('--mongo-username', type=str, default=None, help='user with read/write permissions to --mongo-DB')
parser.add_argument('--mongo-password', type=str, default=None, help='password for --mongo-username')
parser.add_argument('--twitter-auth-key', type=str, default=None, help='auth key for twitter guest session', required=True)
parser.add_argument('--cors-allow', type=str, default=None, help='value for Access-Control-Allow-Origin header')
parser.add_argument('--guest-sessions', type=int, default=10, help='number of Twitter guest sessions to use (default: 10)')
args = parser.parse_args()

TwitterSession.twitter_auth_key = args.twitter_auth_key
guest_session_pool_size = args.guest_sessions

if args.cors_allow is None:
    log.warning('[CORS] Running without CORS headers')
else:
    log.info('[CORS] Allowing requests from: %s', args.cors_allow)

ensure_dir(args.cookie_dir)

log_dir = os.path.dirname(args.log)
ensure_dir(log_dir)
add_file_handler(args.log)

try:
    with open(args.account_file, "r") as f:
        TwitterSession.accounts = json.loads(f.read())
except:
    pass

if args.debug is True:
    set_log_level('debug')
else:
    set_log_level('info')

async def shut_down(app):
    log.info("Closing %d guest sessions", len(TwitterSession.guest_sessions))
    for session in TwitterSession.guest_sessions:
        await session.close()

async def clean_up(app):
    global DB
    log.info("Closing database connection")
    DB.close()

    shutdown_logging()

def run():
    global DB
    DB = connect(
        host=args.mongo_host,
        port=args.mongo_port,
        username=args.mongo_username,
        password=args.mongo_password
    )

    loop = asyncio.get_event_loop()
    loop.run_until_complete(login_accounts(TwitterSession.accounts, args.cookie_dir))
    loop.run_until_complete(login_guests())

    app = web.Application()
    app.add_routes(routes)
    app.on_shutdown.append(shut_down)
    app.on_cleanup.append(clean_up)

    web.run_app(app, host=args.host, port=args.port)

if args.daemon:
    with daemon.DaemonContext():
        run()
else:
    run()
