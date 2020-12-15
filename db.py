import copy
import traceback
import sys
from time import sleep
from pymongo import MongoClient, errors as MongoErrors, DESCENDING

class Database:
    def __init__(self, host=None, port=27017, db='tester', username=None, password=None):
        # collection name definitions
        RESULTS_COLLECTION = 'results'
        RATELIMIT_COLLECTION = 'rate-limits'

        print('[mongoDB] Connecting to ' + host + ':' + str(port))
        print('[mongoDB] Using Database `' + db + '`')
        # client and DB
        self.client = MongoClient(host, port, serverSelectionTimeoutMS=3, username=username, password=password)
        self.db = self.client[db]

        # collections
        self.results = self.db[RESULTS_COLLECTION]
        self.rate_limits = self.db[RATELIMIT_COLLECTION]

        # Test connection immediately, instead of
        # when trying to write in a request, later.
        self.client.admin.command('ismaster')

    def write_result(self, result):
        # copy.deepcopy; otherwise mongo ObjectId (_id) would be added,
        # screwing up later JSON serialisation of results
        self.results.insert_one(copy.deepcopy(result))

    def write_rate_limit(self, data):
        self.rate_limits.insert_one(data)

    def get_result_by_screen_name(self, screen_name):
        return self.results.find_one({ "profile.screen_name": screen_name }, sort=[("_id", DESCENDING)], projection={"_id": False})

    def close(self):
        self.client.close()

def connect(host=None, port=27017, db='tester', username=None, password=None):
    if host is None:
        raise ValueError('[mongoDB] Database constructor needs a `host`name or ip!')

    attempt = 0
    max_attempts = 7
    mongo_client = None

    while (mongo_client is None):
        print('[mongoDB|connect] Connecting, ', attempt, '/', max_attempts)

        try:
            mongo_client = Database(host=host, port=port, db=db, username=username, password=password)
        except Exception as e:
            if attempt is max_attempts:
                raise e

            sleep(attempt)
            attempt += 1

    return mongo_client
