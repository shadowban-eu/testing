import aiohttp
import time
import urllib

from log import log
from statistics import count_sensitives
from typeahead import test as test_typeahead

class UnexpectedApiError(Exception):
    pass

class TwitterSession:
    twitter_auth_key = None
    account_sessions = []
    account_index = 0
    guest_sessions = []
    test_index = 0

    def __init__(self):
        self._guest_token = None
        self._csrf_token = None

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
        cookies = self._session.cookie_jar.filter_cookies('https://twitter.com/')
        for key, cookie in cookies.items():
            if cookie.key == 'ct0':
                self._headers['X-Csrf-Token'] = cookie.value

    async def get_guest_token(self):
        self._headers['Authorization'] = 'Bearer ' + self.twitter_auth_key
        async with self._session.post("https://api.twitter.com/1.1/guest/activate.json", headers=self._headers) as r:
            response = await r.json()
        guest_token = response.get("guest_token", None)
        if guest_token is None:
            log.debug("Failed to fetch guest token")
            log.debug(str(response))
            log.debug(str(self._headers))
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
            log.debug("EXCEPTION: " + str(type(e)))
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

    async def tweet_raw(self, tweet_id, count=20, cursor=None, retry_csrf=True):
        if cursor is None:
            cursor = ""
        else:
            cursor = "&cursor=" + urllib.parse.quote(cursor)
        return await self.get("https://api.twitter.com/2/timeline/conversation/" + tweet_id + ".json?include_reply_count=1&send_error_codes=true&count="+str(count)+ cursor)

    @classmethod
    def flatten_timeline(cls, timeline_items):
        result = []
        for item in timeline_items:
            if get_nested(item, ["content", "item", "content", "tweet", "id"]) is not None:
                result.append(item["content"]["item"]["content"]["tweet"]["id"])
            elif get_nested(item, ["content", "timelineModule", "items"]) is not None:
                timeline_items = item["content"]["timelineModule"]["items"]
                titems = [get_nested(x, ["item", "content", "tweet", "id"]) for x in timeline_items]
                result += [x for x in titems if x is not None]
        return result

    @classmethod
    def get_ordered_tweet_ids(cls, obj, filtered=True):
        try:
            entries = [x for x in obj["timeline"]["instructions"] if "addEntries" in x][0]["addEntries"]["entries"]
        except (IndexError, KeyError):
            return []
        entries.sort(key=lambda x: -int(x["sortIndex"]))
        flat = cls.flatten_timeline(entries)
        return [x for x in flat if not filtered or x in obj["globalObjects"]["tweets"]]

    async def test_ghost_ban(self, user_id):
        try:
            tweets_replies = await self.get_profile_tweets_raw(user_id)
            tweet_ids = self.get_ordered_tweet_ids(tweets_replies)
            replied_ids = []
            for tid in tweet_ids:
                if tweets_replies["globalObjects"]["tweets"][tid]["reply_count"] > 0 and tweets_replies["globalObjects"]["tweets"][tid]["user_id_str"] == user_id:
                    replied_ids.append(tid)

            for tid in replied_ids:
                tweet = await self.tweet_raw(tid)
                for reply_id, reply_obj in tweet["globalObjects"]["tweets"].items():
                    if reply_id == tid or reply_obj.get("in_reply_to_status_id_str", None) != tid:
                        continue
                    reply_tweet = await self.tweet_raw(reply_id)
                    if reply_id not in reply_tweet["globalObjects"]["tweets"]:
                        continue
                    obj = {"tweet": tid, "reply": reply_id}
                    if tid in reply_tweet["globalObjects"]["tweets"]:
                        obj["ban"] = False
                    else:
                        obj["ban"] = True
                    return obj
        except:
            log.debug('Unexpected Exception:')
            log.debug(traceback.format_exc())
            return { "error": "EUNKNOWN" }

    async def test_barrier(self, user_id, screen_name):
        try:
            tweets_replies = await self.get_profile_tweets_raw(user_id)
            tweet_ids = self.get_ordered_tweet_ids(tweets_replies)

            reply_tweet_ids = []

            for tid in tweet_ids:
                if "in_reply_to_status_id_str" not in tweets_replies["globalObjects"]["tweets"][tid] or tweets_replies["globalObjects"]["tweets"][tid]["user_id_str"] != user_id:
                    continue
                tweet = tweets_replies["globalObjects"]["tweets"][tid]
                conversation_tweet = get_nested(tweets_replies, ["globalObjects", "tweets", tweet["conversation_id_str"]])
                if conversation_tweet is not None and conversation_tweet.get("user_id_str") == user_id:
                    continue
                reply_tweet_ids.append(tid)

            # return error message, when user has not made any reply tweets
            if not reply_tweet_ids:
                return {"error": "ENOREPLIES"}

            for tid in reply_tweet_ids:
                replied_to_id = tweets_replies["globalObjects"]["tweets"][tid].get("in_reply_to_status_id_str", None)
                if replied_to_id is None:
                    continue
                replied_tweet_obj = await self.tweet_raw(replied_to_id, 50)
                if "globalObjects" not in replied_tweet_obj:
                    continue
                if replied_to_id not in replied_tweet_obj["globalObjects"]["tweets"]:
                    continue
                replied_tweet = replied_tweet_obj["globalObjects"]["tweets"][replied_to_id]
                if not replied_tweet["conversation_id_str"] in replied_tweet_obj["globalObjects"]["tweets"]:
                    continue
                conversation_tweet = replied_tweet_obj["globalObjects"]["tweets"][replied_tweet["conversation_id_str"]]
                if conversation_tweet["user_id_str"] == user_id:
                    continue
                if replied_tweet["reply_count"] > 500:
                    continue

                log.debug('[' + screen_name + '] Barrier Test: ')
                log.debug('[' + screen_name + '] Found:' + tid)
                log.debug('[' + screen_name + '] In reply to:' + replied_to_id)

                reference_session = next_session()
                reference_session = self
                if reference_session is None:
                    log.debug('No reference session')
                    return

                TwitterSession.account_index += 1

                before_barrier = await reference_session.tweet_raw(replied_to_id, 1000)
                if get_nested(before_barrier, ["globalObjects", "tweets"]) is None:
                    log.debug('notweets\n')
                    return

                if tid in self.get_ordered_tweet_ids(before_barrier):
                    return {"ban": False, "tweet": tid, "in_reply_to": replied_to_id}

                cursors = ["ShowMoreThreads", "ShowMoreThreadsPrompt"]
                last_result = before_barrier

                for stage in range(0, 2):
                    entries = [x for x in last_result["timeline"]["instructions"] if "addEntries" in x][0]["addEntries"]["entries"]

                    try:
                        cursor = [x["content"]["operation"]["cursor"]["value"] for x in entries if get_nested(x, ["content", "operation", "cursor", "cursorType"]) == cursors[stage]][0]
                    except (KeyError, IndexError):
                        continue

                    after_barrier = await reference_session.tweet_raw(replied_to_id, 1000, cursor=cursor)

                    if get_nested(after_barrier, ["globalObjects", "tweets"]) is None:
                        log.debug('retinloop\n')
                        return
                    ids_after_barrier = self.get_ordered_tweet_ids(after_barrier)
                    if tid in self.get_ordered_tweet_ids(after_barrier):
                        return {"ban": True, "tweet": tid, "stage": stage, "in_reply_to": replied_to_id}
                    last_result = after_barrier

                # happens when replied_to_id tweet has been deleted
                log.debug('[' + screen_name + '] outer loop return')
                return { "error": "EUNKNOWN" }
        except:
            log.debug('Unexpected Exception in test_barrier:\n')
            log.debug(traceback.format_exc())
            return { "error": "EUNKNOWN" }

    async def test(self, username):
        result = {"timestamp": time.time()}
        profile = {}
        profile_raw = await self.profile_raw(username)
        log.info('Testing ' + str(username))
        if is_another_error(profile_raw, [50, 63]):
            log.debug("Other error:" + str(username))
            raise UnexpectedApiError

        try:
            user_id = str(profile_raw["id"])
        except KeyError:
            user_id = None

        try:
            profile["screen_name"] = profile_raw["screen_name"]
        except KeyError:
            profile["screen_name"] = username
        try:
            profile["restriction"] = profile_raw["profile_interstitial_type"]
        except KeyError:
            pass
        if profile.get("restriction", None) == "":
            del profile["restriction"]
        try:
            profile["protected"] = profile_raw["protected"]
        except KeyError:
            pass
        profile["exists"] = not is_error(profile_raw, 50)
        suspended = is_error(profile_raw, 63)
        if suspended:
            profile["suspended"] = suspended
        try:
            profile["has_tweets"] = int(profile_raw["statuses_count"]) > 0
        except KeyError:
            profile["has_tweets"] = False

        result["profile"] = profile

        if not profile["exists"] or profile.get("suspended", False) or profile.get("protected", False) or not profile.get('has_tweets'):
            return result

        result["profile"]["sensitives"] = await count_sensitives(self, user_id)

        result["tests"] = {}

        search_raw = await self.search_raw("from:@" + username)

        result["tests"]["search"] = False
        try:
            tweets = search_raw["globalObjects"]["tweets"]
            for tweet_id, tweet in sorted(tweets.items(), key=lambda t: t[1]["id"], reverse=True):
                result["tests"]["search"] = str(tweet_id)
                break

        except (KeyError, IndexError):
            pass

        result["tests"]["typeahead"] = await test_typeahead(self, username)

        if "search" in result["tests"] and result["tests"]["search"] == False:
            result["tests"]["ghost"] = await self.test_ghost_ban(user_id)
        else:
            result["tests"]["ghost"] = {"ban": False}

        if not get_nested(result, ["tests", "ghost", "ban"], False):
            result["tests"]["more_replies"] = await self.test_barrier(user_id, profile['screen_name'])
        else:
            result["tests"]["more_replies"] = { "error": "EISGHOSTED"}

        log.debug('[' + profile['screen_name'] + '] Writing result to DB')
        return result


    async def close(self):
        await self._session.close()

def next_session():
    def key(s):
        remaining_time = s.reset - time.time()
        if s.remaining <= 3 and remaining_time > 0:
            return 900
        return remaining_time
    sessions = sorted([s for s in TwitterSession.account_sessions if not s.locked], key=key)
    if len(sessions) > 0:
        return sessions[0]

def get_nested(obj, path, default=None):
    for p in path:
        if obj is None or not p in obj:
            return default
        obj = obj[p]
    return obj

def is_error(result, code=None):
    return isinstance(result.get("errors", None), list) and (len([x for x in result["errors"] if x.get("code", None) == code]) > 0 or code is None and len(result["errors"] > 0))

def is_another_error(result, codes):
    return isinstance(result.get("errors", None), list) and len([x for x in result["errors"] if x.get("code", None) not in codes]) > 0

