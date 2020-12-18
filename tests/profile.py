from typing import Any

from features import count_sensitives
from log import log
from twitter_session import TwitterSession, UnexpectedApiError
from util import is_error, is_generic_error

async def test(session: TwitterSession, username: str) -> tuple[str, dict[str, Any]]:
    profile: dict[str, Any] = {}
    profile_raw = await session.profile_raw(username)
    log.info('Testing ' + str(username))
    if is_generic_error(profile_raw, [50, 63]):
        log.debug("Other error:" + str(username))
        raise UnexpectedApiError

    try:
        user_id = str(profile_raw["id"])
    except KeyError:
        user_id = ''

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

    profile["sensitives"] = await count_sensitives(session, user_id)

    return user_id, profile
