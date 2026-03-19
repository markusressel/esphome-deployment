FROM python:3.14-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    POETRY_VERSION="2.3.2" \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    VENV_HOME=/opt/poetry \
    ESPHOME_VERSION="2026.2.4" \
    PLATFORMIO_CORE_DIR=/config/.platformio

RUN groupadd -g 1000 deployer && \
    useradd -u 1000 -g deployer -m -s /bin/bash deployer && \
    apt-get update && \
    apt-get -y upgrade && \
    apt-get -y install --no-install-recommends git python3-pip && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="${VENV_HOME}/bin:${PATH}"
WORKDIR /app

RUN python3 -m venv ${VENV_HOME} && \
    chown -R deployer:deployer ${VENV_HOME} && \
    mkdir -p /config && chown -R deployer:deployer /config

USER deployer

COPY --chown=deployer:deployer README.md poetry.lock pyproject.toml ./
COPY --chown=deployer:deployer esphome_deployment esphome_deployment
COPY --chown=deployer:deployer README.md esphome_deployment/README.md

RUN ${VENV_HOME}/bin/pip install --upgrade pip setuptools && \
    ${VENV_HOME}/bin/pip install "poetry==${POETRY_VERSION}" && \
    ${VENV_HOME}/bin/poetry check && \
    POETRY_VIRTUALENVS_CREATE=false ${VENV_HOME}/bin/poetry install --no-interaction --no-cache --only main --no-root && \
    ${VENV_HOME}/bin/pip install "esphome==${ESPHOME_VERSION}" && \
    ${VENV_HOME}/bin/pip install . && \
    ${VENV_HOME}/bin/pip uninstall -y poetry

WORKDIR /config

CMD [ "esphome-deployment" ]