FROM python:3.7-slim-buster

RUN mkdir /app
ADD . /app

WORKDIR /app
RUN ./bin/install.sh
