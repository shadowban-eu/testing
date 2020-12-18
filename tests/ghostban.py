import traceback

from log import log

async def test(session, user_id):
    try:
        tweets_replies = await session.get_profile_tweets_raw(user_id)
        tweet_ids = session.get_ordered_tweet_ids(tweets_replies)
        replied_ids = []
        for tid in tweet_ids:
            if tweets_replies["globalObjects"]["tweets"][tid]["reply_count"] > 0 and tweets_replies["globalObjects"]["tweets"][tid]["user_id_str"] == user_id:
                replied_ids.append(tid)

        for tid in replied_ids:
            tweet = await session.tweet_raw(tid)
            for reply_id, reply_obj in tweet["globalObjects"]["tweets"].items():
                if reply_id == tid or reply_obj.get("in_reply_to_status_id_str", None) != tid:
                    continue
                reply_tweet = await session.tweet_raw(reply_id)
                if reply_id not in reply_tweet["globalObjects"]["tweets"]:
                    continue
                obj = {"tweet": tid, "reply": reply_id}
                if tid in reply_tweet["globalObjects"]["tweets"]:
                    obj["ban"] = False
                else:
                    obj["ban"] = True
                return obj
    except:
        log.error('Unexpected Exception:')
        log.error(traceback.format_exc())
        return { "error": "EUNKNOWN" }
