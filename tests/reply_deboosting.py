import traceback

from log import log
from util import get_nested, get_ordered_tweet_ids

async def test(session, user_id, screen_name):
    try:
        tweets_replies = await session.get_profile_tweets_raw(user_id)
        tweet_ids = get_ordered_tweet_ids(tweets_replies)

        reply_tweet_ids = []

        for tid in tweet_ids:
            tweet = tweets_replies["globalObjects"]["tweets"][tid]
            if "in_reply_to_status_id_str" not in tweet or tweet["in_reply_to_user_id_str"] == user_id or tweet["user_id_str"] != user_id:
                continue
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
            replied_tweet_obj = await session.tweet_raw(replied_to_id, 50)
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

            if session is None:
                log.critical('No reference session')
                return

            # Importing TwitterSession directly creates circular import
            session.__class__.account_index += 1

            before_barrier = await session.tweet_raw(replied_to_id, 1000)
            if get_nested(before_barrier, ["globalObjects", "tweets"]) is None:
                log.error('notweets')
                return

            if tid in get_ordered_tweet_ids(before_barrier):
                return {"ban": False, "tweet": tid, "in_reply_to": replied_to_id}

            cursors = ["ShowMoreThreads", "ShowMoreThreadsPrompt"]
            last_result = before_barrier

            for stage in range(0, 2):
                entries = [x for x in last_result["timeline"]["instructions"] if "addEntries" in x][0]["addEntries"]["entries"]

                try:
                    cursor = [x["content"]["operation"]["cursor"]["value"] for x in entries if get_nested(x, ["content", "operation", "cursor", "cursorType"]) == cursors[stage]][0]
                except (KeyError, IndexError):
                    continue

                after_barrier = await session.tweet_raw(replied_to_id, 1000, cursor=cursor)

                if get_nested(after_barrier, ["globalObjects", "tweets"]) is None:
                    log.error('retinloop')
                    return
                ids_after_barrier = get_ordered_tweet_ids(after_barrier)
                if tid in get_ordered_tweet_ids(after_barrier):
                    return {"ban": True, "tweet": tid, "stage": stage, "in_reply_to": replied_to_id}
                last_result = after_barrier

            # happens when replied_to_id tweet has been deleted
            log.error('[' + screen_name + '] outer loop return')
            return { "error": "EUNKNOWN" }
    except:
        log.error('Unexpected Exception in test_barrier:')
        log.error(traceback.format_exc())
        return { "error": "EUNKNOWN" }
