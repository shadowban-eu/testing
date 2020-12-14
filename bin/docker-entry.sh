#!/usr/bin/env bash

source ./_venv

if [ "$1" != "" ] && [ -f $1 ]; then
  echo "Using provided .env file: $1"
  export $(cat $1 | xargs)
  shift
fi

echo "Starting server..."
echo "--account-file $ACCOUNT_FILE"
echo "--cookie-dir $COOKIE_DIR"
echo "--log $LOG_FILE"
echo "--debug $DEBUG_FILE"
echo "--port "$PORT""
echo "--host "$HOST""
echo "--mongo-host $MONGO_HOST"
echo "--mongo-port $MONGO_PORT"
echo "--mongo-db $MONGO_DB"
echo "--mongo-username $MONGO_USERNAME"
echo "--mongo-password --REDACTED--"
echo "--twitter-auth-key --REDACTED--"
echo "--cors-allow $CORS_HOST"
echo "--guest-sessions $GUEST_SESSIONS"

CMD="python3 -u ./backend.py"

if [ "$1" == "mprof" ]; then
  shift
  CMD="mprof run $@ ./backend.py"
  echo -e "\nRecording memory profile\n"
fi

$CMD \
  --account-file $ACCOUNT_FILE \
  --cookie-dir $COOKIE_DIR \
  --log $LOG_FILE \
  --debug $DEBUG_FILE \
  --port "$PORT" \
  --host "$HOST" \
  --mongo-host $MONGO_HOST \
  --mongo-port $MONGO_PORT \
  --mongo-db $MONGO_DB \
  --mongo-username $MONGO_USERNAME \
  --mongo-password $MONGO_PASSWORD \
  --twitter-auth-key $TWITTER_AUTH_KEY \
  --cors-allow $CORS_HOST \
  --guest-sessions $GUEST_SESSIONS
