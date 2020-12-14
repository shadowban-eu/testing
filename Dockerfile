FROM python:3.5.7-slim-buster

RUN mkdir /app
ADD . /app

WORKDIR /app
RUN ./install.sh
