from typing import Any
import time
import urllib, urllib.parse
import os

import aiohttp
from bs4 import BeautifulSoup
from yarl import URL

from log import log
from tests import *
from util import get_nested, is_error

class UnexpectedApiError(Exception):
    pass

class TwitterSession:
    twitter_auth_key = ''
    account_sessions = []
    account_index = 0
    guest_sessions = []
    test_index = 0
    accounts = []

    def __init__(self):
        self._guest_token = ''
        self._csrf_token = ''

        # aiohttp ClientSession
        self._session = None

        # rate limit monitoring
        self.remaining = 180
        self.reset = -1
        self.locked = False
        self.next_refresh = None

        # session user's @username
        # this stays `None` for guest sessions
        self.username = None

        self._headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36"
        }
        # sets self._headers
        self.reset_headers()

    def set_csrf_header(self):
        cookies = self._session.cookie_jar.filter_cookies(URL('https://twitter.com/'))
        for _, cookie in cookies.items():
            if cookie.key == 'ct0':
                self._headers['X-Csrf-Token'] = cookie.value

    async def get_guest_token(self):
        self._headers['Authorization'] = 'Bearer ' + self.twitter_auth_key
        async with self._session.post("https://api.twitter.com/1.1/guest/activate.json", headers=self._headers) as r:
            response = await r.json()
        guest_token = response.get("guest_token", None)
        if guest_token is None:
            log.error("Failed to fetch guest token")
            log.error(str(response))
            log.error(str(self._headers))
        return guest_token

    def reset_headers(self):
        self._headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36"
        }

    async def renew_session(self):
        await self.try_close()
        self._session = aiohttp.ClientSession()
        self.reset_headers()

    async def refresh_old_token(self):
        if self.username is not None or self.next_refresh is None or time.time() < self.next_refresh:
            return
        log.debug("Refreshing token: " + str(self._guest_token))
        await self.login_guest()
        log.debug("New token: " + str(self._guest_token))

    async def try_close(self):
        if self._session is not None:
            try:
                await self._session.close()
            except:
                pass

    async def login_guest(self):
        await self.renew_session()
        self.set_csrf_header()
        old_token = self._guest_token
        new_token = await self.get_guest_token()
        self._guest_token = new_token if new_token is not None else old_token
        if new_token is not None:
            self.next_refresh = time.time() + 3600
        self._headers['X-Guest-Token'] = self._guest_token

    async def login(self, username = None, password = None, email = None, cookie_dir=None):
        self._session = aiohttp.ClientSession()

        if password is not None:
            login_required = True
            cookie_file = None
            if cookie_dir is not None:
                cookie_file = os.path.join(cookie_dir, username)
                if os.path.isfile(cookie_file):
                    log.info("Use cookie file for %s" % username)
                    # satisfy linter; https://github.com/aio-libs/aiohttp/issues/4043#issuecomment-529085744
                    assert isinstance(self._session.cookie_jar, aiohttp.CookieJar)
                    self._session.cookie_jar.load(cookie_file)
                    login_required = False

            store_cookies = True

            if login_required:
                async with self._session.get("https://twitter.com/login", headers=self._headers) as r:
                    login_page = await r.text()
                form_data = {}
                soup = BeautifulSoup(login_page, 'html.parser')
                form_data["authenticity_token"] = soup.find('input', {'name': 'authenticity_token'}).get('value')
                form_data["session[username_or_email]"] = email
                form_data["session[password]"] = password
                form_data["remember_me"] = "1"
                async with self._session.post('https://twitter.com/sessions', data=form_data, headers=self._headers) as r:
                    response = await r.text()
                    if str(r.url) == "https://twitter.com/":
                        log.info("Login of %s successful" % username)
                    else:
                        store_cookies = False
                        log.info("Error logging in %s (%s)" % (username, r.url))
                        log.debug("ERROR PAGE\n" + response)
            else:
                async with self._session.get('https://twitter.com', headers=self._headers) as r:
                    await r.text()

            self.set_csrf_header()
            self.username = username

            if cookie_file is not None and store_cookies:
                # satisfy linter; https://github.com/aio-libs/aiohttp/issues/4043#issuecomment-529085744
                assert isinstance(self._session.cookie_jar, aiohttp.CookieJar)
                self._session.cookie_jar.save(cookie_file)

        else:
            await self.login_guest()

        self._headers['Authorization'] = 'Bearer ' + self.twitter_auth_key

    async def get(self, url, retries=0):
        self.set_csrf_header()
        await self.refresh_old_token()
        try:
            async with self._session.get(url, headers=self._headers) as r:
                result = await r.json()
        except Exception as e:
            log.error("EXCEPTION: %s", str(type(e)))
            if self.username is None:
                await self.login_guest()
            raise e
        if self.username is None and self.remaining < 10 or is_error(result, 88) or is_error(result, 239):
            await self.login_guest()
        if retries > 0 and is_error(result, 353):
            return await self.get(url, retries - 1)
        if is_error(result, 326):
            self.locked = True
        return result

    async def search_raw(self, query, live=True):
        additional_query = ""
        if live:
            additional_query = "&tweet_search_mode=live"
        return await self.get("https://api.twitter.com/2/search/adaptive.json?q="+urllib.parse.quote(query)+"&count=20&spelling_corrections=0" + additional_query)

    async def profile_raw(self, username):
        return await self.get("https://api.twitter.com/1.1/users/show.json?screen_name=" + urllib.parse.quote(username))

    async def get_profile_tweets_raw(self, user_id):
        return await self.get("https://api.twitter.com/2/timeline/profile/" + str(user_id) +".json?include_tweet_replies=1&include_want_retweets=0&include_reply_count=1&count=1000")

    async def tweet_raw(self, tweet_id, count=20, cursor=None):
        if cursor is None:
            cursor = ""
        else:
            cursor = "&cursor=" + urllib.parse.quote(cursor)
        return await self.get("https://api.twitter.com/2/timeline/conversation/" + tweet_id + ".json?include_reply_count=1&send_error_codes=true&count="+str(count)+ cursor)

    async def test(self, username):
        result: dict[str, Any] = {"timestamp": time.time()}
        user_id, profile = await test_profile(self, username)
        result["profile"] = profile

        if not profile["exists"] or profile.get("suspended", False) or profile.get("protected", False) or not profile.get('has_tweets'):
            return result

        result["tests"] = {}

        search_raw = await self.search_raw("from:@" + username)

        result["tests"]["search"] = False
        try:
            tweets = search_raw["globalObjects"]["tweets"]
            for tweet_id, _ in sorted(tweets.items(), key=lambda t: t[1]["id"], reverse=True):
                result["tests"]["search"] = str(tweet_id)
                break

        except (KeyError, IndexError):
            pass

        result["tests"]["typeahead"] = await test_typeahead(self, username)

        if "search" in result["tests"] and result["tests"]["search"] == False:
            result["tests"]["ghost"] = await test_ghost_ban(self, user_id)
        else:
            result["tests"]["ghost"] = {"ban": False}

        if not get_nested(result, ["tests", "ghost", "ban"], False):
            result["tests"]["more_replies"] = await test_reply_deboosting(self, user_id, profile['screen_name'])
        else:
            result["tests"]["more_replies"] = { "error": "EISGHOSTED"}

        log.debug('[' + profile['screen_name'] + '] Writing result to DB')
        return result


    async def close(self):
        await self._session.close()

# unused
def next_session():
    def key(s):
        remaining_time = s.reset - time.time()
        if s.remaining <= 3 and remaining_time > 0:
            return 900
        return remaining_time
    sessions = sorted([s for s in TwitterSession.account_sessions if not s.locked], key=key)
    if len(sessions) > 0:
        return sessions[0]
