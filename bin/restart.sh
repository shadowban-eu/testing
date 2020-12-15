if [ "$1" != "" ] && [ -f $1 ]; then
  ENV_FILE=$1
else
  ENV_FILE=.env
fi

echo 'Stopping service'
pkill -f twitter-auth-key
if [ $? -ne 0 ]; then
  echo "Service not running"
fi

if [ "$1" == "-k" ]; then
    echo "Deleting logs"
    rm ./logs/*
fi

echo 'Starting service'
./docker-entry.sh $ENV_FILE
