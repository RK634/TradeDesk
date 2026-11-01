FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app \
    && mkdir -p /app/.private_storage \
    && chown -R app:app /app/.private_storage
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
