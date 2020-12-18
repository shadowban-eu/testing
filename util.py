def get_nested(obj, path, default=None):
    for p in path:
        if obj is None or not p in obj:
            return default
        obj = obj[p]
    return obj

def is_error(result, code=None):
    return isinstance(result.get("errors", None), list) and (len([x for x in result["errors"] if x.get("code", None) == code]) > 0 or code is None and len(result["errors"] > 0))

def is_generic_error(result, codes):
    return isinstance(result.get("errors", None), list) and len([x for x in result["errors"] if x.get("code", None) not in codes]) > 0

def flatten_timeline(timeline_items):
    result = []
    for item in timeline_items:
        if get_nested(item, ["content", "item", "content", "tweet", "id"]) is not None:
            result.append(item["content"]["item"]["content"]["tweet"]["id"])
        elif get_nested(item, ["content", "timelineModule", "items"]) is not None:
            timeline_items = item["content"]["timelineModule"]["items"]
            titems = [get_nested(x, ["item", "content", "tweet", "id"]) for x in timeline_items]
            result += [x for x in titems if x is not None]
    return result

def get_ordered_tweet_ids(obj, filtered=True):
    try:
        entries = [x for x in obj["timeline"]["instructions"] if "addEntries" in x][0]["addEntries"]["entries"]
    except (IndexError, KeyError):
        return []
    entries.sort(key=lambda x: -int(x["sortIndex"]))
    flat = flatten_timeline(entries)
    return [x for x in flat if not filtered or x in obj["globalObjects"]["tweets"]]
