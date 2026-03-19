FROM python:3.14-slim-bookworm

ENV PYTHONUNBUFFERED=1
ENV POETRY_VERSION="2.3.2"
ENV PIP_DISABLE_PIP_VERSION_CHECK=on
ENV VENV_HOME=/opt/poetry
WORKDIR /app

# Add Poetry to PATH
ENV PATH="${VENV_HOME}/bin:${PATH}"

COPY README.md poetry.lock pyproject.toml ./
COPY esphome_deployment esphome_deployment
COPY README.md esphome_deployment/README.md

RUN apt-get update \
 && apt-get -y install python3-pip \
 && apt-get clean && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv ${VENV_HOME} \
 && ${VENV_HOME}/bin/pip install --upgrade pip setuptools \
 && ${VENV_HOME}/bin/pip install "poetry==${POETRY_VERSION}" \
 && ${VENV_HOME}/bin/poetry check \
 && POETRY_VIRTUALENVS_CREATE=false ${VENV_HOME}/bin/poetry install --no-interaction --no-cache --only main \
 && ${VENV_HOME}/bin/pip uninstall -y poetry

WORKDIR /config

CMD [ "esphome-deployment" ]
