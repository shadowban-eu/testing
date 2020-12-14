#!/usr/bin/env bash

source ./_venv

echo "Installing dependencies..."
pip3 install -r requirements.txt --no-cache-dir

if [ $? -eq 0 ]; then
  echo -e "\n----------------------------"
  echo -e "Almost done! \\o/\n"
  echo "Run 'PYTHON_ENV=[development|prodcution] ./docker-entry.sh .env.example' to start the server!"
  echo -e "\nIf you want to make changes to the python packages, e.g. 'pip3 install ...', activate the venv, first: '. .venv/bin/activate'"
fi
