FROM python:3.13-slim

RUN --mount=type=cache,target=/var/cache/apt \
    apt-get -y update && \
    apt-get -y install git build-essential zlib1g-dev

RUN --mount=type=cache,target=/root/.cache/pip \
    ([ -d /venv ] || python3.13 -m venv /venv) && \
    /venv/bin/pip install --upgrade pip

WORKDIR /workspace/
ADD pyproject.toml pyproject.toml
ARG PSEUDO_VERSION=1
RUN --mount=type=cache,target=/root/.cache/pip \
    SETUPTOOLS_SCM_PRETEND_VERSION=${PSEUDO_VERSION} \
    /venv/bin/pip install -e .
RUN --mount=source=.git,target=.git,type=bind \
    --mount=type=cache,target=/root/.cache/pip \
    /venv/bin/pip install -e .

ADD . .

ENTRYPOINT ["/venv/bin/python", "-m", "archive_query_log"]
