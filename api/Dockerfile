FROM python:3.13-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY api/requirements.lock api/requirements.lock
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r api/requirements.lock
COPY packages/contracts packages/contracts
COPY api api
RUN pip install --no-cache-dir --no-deps ./packages/contracts ./api
RUN pip check

FROM python:3.13-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PAPILIO_CONFIG=/app/config.yml.sample
WORKDIR /app
RUN useradd --uid 10001 --create-home her
COPY --from=build /opt/venv /opt/venv
COPY api/alembic.ini api/alembic.ini
COPY api/migrations api/migrations
COPY config.yml.sample config.yml.sample
USER her
CMD ["uvicorn", "her_api.apps.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
