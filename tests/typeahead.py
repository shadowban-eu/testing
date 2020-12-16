import urllib.parse

async def test(session, screen_name):
  query = "@" + screen_name
  suggestions = await session.get("https://api.twitter.com/1.1/search/typeahead.json?src=search_box&result_type=users&q=" + urllib.parse.quote(query))
  try:
    result = len([1 for user in suggestions["users"] if user["screen_name"].lower() == screen_name.lower()]) > 0
  except:
    result = False

  return result
