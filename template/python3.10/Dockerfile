FROM ghcr.io/openfaas/of-watchdog:0.9.2 as watchdog
FROM python:3.10-alpine

COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
RUN chmod +x /usr/bin/fwatchdog

ARG ADDITIONAL_PACKAGE
# Alternatively use ADD https:// (which will not be cached by Docker builder)

RUN apk --no-cache add ca-certificates gcc libc-dev libffi-dev ${ADDITIONAL_PACKAGE}

# Add non root user
RUN addgroup -S app && adduser app -S -G app

WORKDIR /home/app

COPY index.py requirements.txt ./

RUN mkdir -p /home/app/python  \
    && chown -R app /home/app

USER app

ENV PATH=$PATH:/home/app/.local/bin:/home/app/python/bin
ENV PYTHONPATH=$PYTHONPATH:/home/app/python

RUN pip install -r requirements.txt --target=/home/app/python

RUN mkdir -p function
RUN touch ./function/__init__.py
WORKDIR /home/app/function/
COPY function/requirements.txt .
RUN pip install -r requirements.txt --target=/home/app/python

WORKDIR /home/app/

#install function code
USER root

COPY function function
RUN chown -R app:app ./ \
    && chmod -R 777 /home/app/python

USER app

ENV fprocess="python index.py"
EXPOSE 8080

HEALTHCHECK --interval=5s CMD [ -e /tmp/.lock ] || exit 1

CMD ["fwatchdog"]
