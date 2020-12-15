FROM python:3.7-slim-buster

RUN apt update
RUN apt install gcc python3-dev -y

RUN mkdir /app
ADD . /app

ENV NO_VENV=1
WORKDIR /app
RUN ./bin/install.sh
