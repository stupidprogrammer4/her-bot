FROM python:3.13-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY bots/requirements.lock bots/requirements.lock
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r bots/requirements.lock
COPY packages/contracts packages/contracts
COPY bots bots
RUN pip install --no-cache-dir --no-deps ./packages/contracts ./bots
RUN pip check

FROM python:3.13-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN useradd --uid 10001 --create-home her
COPY --from=build /opt/venv /opt/venv
USER her
CMD ["python", "-m", "her_bot"]
