FROM python:3.6-alpine

RUN apk --update --no-cache add gcc g++ musl-dev libuv libffi-dev make postgresql-dev \
 && rm -rf /var/cache/apk/*

ADD ./main.py /home/root/main.py

ENV IMAGE_NAME mithra_proxy
WORKDIR /home/root
ENV PYTHONUNBUFFERED 1
ENTRYPOINT ["./main.py"]
