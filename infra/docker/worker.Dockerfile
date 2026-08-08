FROM python:3.11-slim

WORKDIR /app

COPY libs/concord-core /app/libs/concord-core
RUN pip install --no-cache-dir /app/libs/concord-core

COPY services/worker /app/services/worker
RUN pip install --no-cache-dir /app/services/worker

COPY infra/sql /app/infra/sql

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "concord_worker.main"]