FROM python:3.11-slim

WORKDIR /app

COPY libs/concord-core /app/libs/concord-core
RUN pip install --no-cache-dir /app/libs/concord-core

COPY services/reconciler /app/services/reconciler
RUN pip install --no-cache-dir /app/services/reconciler

COPY infra/sql /app/infra/sql

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "concord_reconciler.main"]