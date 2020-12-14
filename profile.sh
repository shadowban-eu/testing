mprof run ./backend.py \
  --account-file ./.htaccounts \
  --cookie-dir ./.htcookies \
  --port 8080 \
  --host 0.0.0.0 \
  --mongo-host 127.0.0.1 \
  --mongo-port 27017 \
  --mongo-db tester \
  --mongo-username $MONGO_USERNAME \
  --mongo-password $MONGO_PASSWORD \
  --twitter-auth-key AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA \
  --guest-sessions $GUEST_SESSIONS