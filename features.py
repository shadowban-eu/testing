# Count amount of "possibly_sensitive_editable" and "possibly_sensitive"
# flagged tweets in user's timeline
async def count_sensitives(session, user_id):
  profile_timeline = await session.get_profile_tweets_raw(user_id)
  profile_tweets = profile_timeline["globalObjects"]["tweets"].values()

  counted = len(profile_tweets)
  possibly_sensitive = len([1 for tweet in profile_tweets if "possibly_sensitive" in tweet.keys()])
  possibly_sensitive_editable = len([1 for tweet in profile_tweets if "possibly_sensitive_editable" in tweet.keys()])

  result = {
    "counted": counted,
    "possibly_sensitive": possibly_sensitive,
    "possibly_sensitive_editable": possibly_sensitive_editable
  }

  return result
