import copy
from time import sleep
from pymongo import MongoClient

from log import log

class Database:
    def __init__(self, host=None, port=27017, db='tester', username=None, password=None):
        # collection name definitions
        RESULTS_COLLECTION = 'results'
        RATELIMIT_COLLECTION = 'rate-limits'

        log.info('Connecting to %s:%d', host, port)
        log.info('Using Database `%s`', db)
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

    def close(self):
        self.client.close()

def connect(host=None, port=27017, db='tester', username=None, password=None):
    if host is None:
        raise ValueError('Database constructor needs a `host`name or ip!')

    attempt = 0
    max_attempts = 7
    mongo_client = None

    while (mongo_client is None):
        try:
            mongo_client = Database(host=host, port=port, db=db, username=username, password=password)
        except Exception as e:
            if attempt is max_attempts:
                raise e

            sleep(attempt)
            attempt += 1
            log.warn('Retrying connection, %s/%s', attempt, max_attempts)

    return mongo_client
