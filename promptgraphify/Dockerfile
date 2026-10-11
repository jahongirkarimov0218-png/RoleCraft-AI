# syntax=docker/dockerfile:1
# Two targets: `api` (FastAPI + the analyzer) and `web` (the Next.js UI). docker-compose.yml builds both.
#   docker build --target api -t promptgraphify-api .
#   docker build --target web -t promptgraphify-web --build-arg PROMPTGRAPHIFY_API_URL=http://api:8000 .
ARG PYTHON_VERSION=3.13
ARG NODE_VERSION=22

# ------------------------------------------------------------------------------------------------ api
FROM python:${PYTHON_VERSION}-slim AS api
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# Dependencies exactly as locked in uv.lock (requirements.txt is `uv export`, with hashes); then the project itself.
COPY requirements.txt ./
RUN pip install --require-hashes -r requirements.txt
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-deps .
RUN useradd --create-home --uid 10001 app && mkdir /data && chown app /data
USER app
ENV PROMPTGRAPHIFY_DB=/data/graphs.sqlite3
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status == 200 else 1)"
# Binds all interfaces *inside the container*; compose publishes nothing from this service. The API has no authentication.
CMD ["uvicorn", "promptgraphify.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

# ------------------------------------------------------------------------------------------------ web
FROM node:${NODE_VERSION}-slim AS web-build
WORKDIR /web
ENV NEXT_TELEMETRY_DISABLED=1
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
# Next bakes the /api proxy destination into the build.
ARG PROMPTGRAPHIFY_API_URL=http://api:8000
ENV PROMPTGRAPHIFY_API_URL=${PROMPTGRAPHIFY_API_URL}
RUN npm run build

FROM node:${NODE_VERSION}-slim AS web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
WORKDIR /web
COPY --from=web-build /web/package.json /web/package-lock.json ./
RUN npm ci --omit=dev
COPY --from=web-build /web/.next ./.next
COPY --from=web-build /web/next.config.mjs ./
USER node
EXPOSE 3000
CMD ["npx", "next", "start", "-p", "3000", "-H", "0.0.0.0"]
