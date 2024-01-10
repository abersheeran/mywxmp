FROM python:3.12 as requirements

WORKDIR /src

RUN python -m pip install -U pdm

RUN pdm config python.use_venv False

COPY pyproject.toml pyproject.toml
COPY pdm.lock pdm.lock

RUN pdm export --production -f requirements -o requirements.txt --without-hashes

FROM python:3.12

WORKDIR /src

ENV PYTHONDONTWRITEBYTECODE 1

COPY --from=requirements /src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
