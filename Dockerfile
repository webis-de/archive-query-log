FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN \
    --mount=type=cache,target=/var/cache/apt \
    apt-get update -y && \
    apt-get upgrade -y
RUN \
    --mount=type=cache,target=/var/cache/apt \
    apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa
RUN \
    --mount=type=cache,target=/var/cache/apt \
    apt-get install -y python3.10 python3.10-dev python3.10-venv git build-essential zlib1g-dev protobuf-compiler

RUN \
    --mount=type=cache,target=/root/.cache/pip \
    ([ -d /venv ] || python3.10 -m venv /venv) && \
    /venv/bin/pip install --upgrade pip

WORKDIR /workspace/
ADD pyproject.toml pyproject.toml
ARG PSEUDO_VERSION=1
RUN \
    --mount=type=cache,target=/root/.cache/pip \
    SETUPTOOLS_SCM_PRETEND_VERSION=${PSEUDO_VERSION} \
    /venv/bin/pip install -e .

RUN \
    --mount=source=.git,target=.git,type=bind \
    --mount=type=cache,target=/root/.cache/pip \
    /venv/bin/pip install -e .

ADD . .

ENTRYPOINT ["/venv/bin/python", "-m", "archive_query_log"]