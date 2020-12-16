#!/usr/bin/env bash

source ./bin/_venv

if [ "$1" != "" ] && [ -f $1 ]; then
  echo "Using provided .env file: $1"
  export $(cat $1 | xargs)
  shift
fi

CMD="python3 -u ./backend.py"

if [ "$1" == "mprof" ]; then
  shift
  CMD="mprof run $@ ./backend.py"
  echo -e "\nRecording memory profile\n"
fi

SERVICE_ARGS="\
  --account-file $ACCOUNT_FILE \
  --cookie-dir $COOKIE_DIR \
  --log $LOG_FILE \
  --port "$PORT" \
  --host "$HOST" \
  --mongo-host $MONGO_HOST \
  --mongo-port $MONGO_PORT \
  --mongo-db $MONGO_DB \
  --mongo-username $MONGO_USERNAME \
  --mongo-password $MONGO_PASSWORD \
  --twitter-auth-key $TWITTER_AUTH_KEY \
  --cors-allow $CORS_ALLOW \
  --guest-sessions $GUEST_SESSIONS \
"

if [ -n "$DEBUG" ]; then
  SERVICE_ARGS="$SERVICE_ARGS --debug"
fi

CMD="$CMD $SERVICE_ARGS $@"
echo -n "Starting server: "
if [ -n "$DEBUG" ]; then
  echo $CMD
else
  echo ""
fi
$CMD
