import aiohttp
import argparse
import asyncio
import daemon
import json
import os
import re
import traceback
import urllib.parse
import sys
import time

from aiohttp import web
from bs4 import BeautifulSoup

from twitter_session import TwitterSession
from db import connect

log_file = None
debug_file = None
db = None

routes = web.RouteTableDef()

def debug(message):
    if message.endswith('\n') is False:
        message = message + '\n'

    if debug_file is not None:
        debug_file.write(message)
        debug_file.flush()
    else:
        print(message)

def log(message):
    # ensure newline
    if message.endswith('\n') is False:
         message = message + '\n'

    if log_file is not None:
        log_file.write(message)
        log_file.flush()
    else:
        print(message)

def print_session_info(sessions):
    text = ""
    for session in sessions:
        text += "\n%6d %5d %9d %5d" % (int(session.locked), session.limit, session.remaining, session.reset - int(time.time()))
    return text

@routes.get('/.stats')
async def stats(request):
    text = "--- GUEST SESSIONS ---\n\nLocked Limit Remaining Reset"
    text += print_session_info(TwitterSession.guest_sessions)
    text += "\n\n\n--- ACCOUNTS ---\n\nLocked Limit Remaining Reset"
    text += print_session_info(TwitterSession.account_sessions)
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
    if screen_name == "wikileaks" and request.query_string != "watch":
        debug("[wikileaks] Returning last watch result")
        db_result = db.get_result_by_screen_name("wikileaks")
        return web.json_response(db_result, headers={"Access-Control-Allow-Origin": args.cors_allow})
    session = TwitterSession.guest_sessions[TwitterSession.test_index % len(TwitterSession.guest_sessions)]
    TwitterSession.test_index += 1
    result = await session.test(screen_name)
    db.write_result(result)
    log(json.dumps(result) + '\n')
    if (args.cors_allow is not None):
        return web.json_response(result, headers={"Access-Control-Allow-Origin": args.cors_allow})
    else:
        return web.json_response(result)

async def login_accounts(accounts, cookie_dir=None):
    if cookie_dir is not None and not os.path.isdir(cookie_dir):
        os.mkdir(cookie_dir, 0o700)
    coroutines = []
    for acc in accounts:
        session = TwitterSession()
        coroutines.append(session.login(*acc, cookie_dir=cookie_dir))
        TwitterSession.account_sessions.append(session)
    await asyncio.gather(*coroutines)

async def login_guests():
    for i in range(0, guest_session_pool_size):
        session = TwitterSession()
        TwitterSession.guest_sessions.append(session)
    await asyncio.gather(*[s.login() for s in TwitterSession.guest_sessions])
    log("Guest sessions created")

def ensure_dir(path):
    if os.path.isdir(path) is False:
        print('Creating directory %s' % path)
        os.mkdir(path)

parser = argparse.ArgumentParser(description='Twitter Shadowban Tester')
parser.add_argument('--account-file', type=str, default='.htaccounts', help='json file with reference account credentials')
parser.add_argument('--cookie-dir', type=str, default=None, help='directory for session account storage')
parser.add_argument('--log', type=str, default=None, help='log file where test results are written to')
parser.add_argument('--daemon', action='store_true', help='run in background')
parser.add_argument('--debug', type=str, default=None, help='debug log file')
parser.add_argument('--port', type=int, default=8080, help='port which to listen on')
parser.add_argument('--host', type=str, default='127.0.0.1', help='hostname/ip which to listen on')
parser.add_argument('--mongo-host', type=str, default='localhost', help='hostname or IP of mongoDB service to connect to')
parser.add_argument('--mongo-port', type=int, default=27017, help='port of mongoDB service to connect to')
parser.add_argument('--mongo-db', type=str, default='tester', help='name of mongo database to use')
parser.add_argument('--mongo-username', type=str, default=None, help='user with read/write permissions to --mongo-db')
parser.add_argument('--mongo-password', type=str, default=None, help='password for --mongo-username')
parser.add_argument('--twitter-auth-key', type=str, default=None, help='auth key for twitter guest session', required=True)
parser.add_argument('--cors-allow', type=str, default=None, help='value for Access-Control-Allow-Origin header')
parser.add_argument('--guest-sessions', type=int, default=10, help='number of Twitter guest sessions to use')
args = parser.parse_args()

TwitterSession.twitter_auth_key = args.twitter_auth_key
guest_session_pool_size = args.guest_sessions

if (args.cors_allow is None):
    debug('[CORS] Running without CORS headers')
else:
    debug('[CORS] Allowing requests from: ' + args.cors_allow)

ensure_dir(args.cookie_dir)

try:
    with open(args.account_file, "r") as f:
        accounts = json.loads(f.read())
except:
    accounts = []

if args.log is not None:
    print("Logging test results to %s" % args.log)
    log_dir = os.path.dirname(args.log)
    ensure_dir(log_dir)
    log_file = open(args.log, "a")

if args.debug is not None:
    print("Logging debug output to %s" % args.debug)
    debug_dir = os.path.dirname(args.debug)
    ensure_dir(debug_dir)
    debug_file = open(args.debug, "a")

def run():
    global db
    db = connect(
        host=args.mongo_host,
        port=args.mongo_port,
        username=args.mongo_username,
        password=args.mongo_password
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(login_accounts(accounts, args.cookie_dir))
    loop.run_until_complete(login_guests())
    app = web.Application()
    app.add_routes(routes)
    web.run_app(app, host=args.host, port=args.port)

if args.daemon:
    with daemon.DaemonContext():
        run()
else:
    run()
