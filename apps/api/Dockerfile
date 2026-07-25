# Built with repo-root context (see infra/docker-compose.yml: context: .., dockerfile:
# apps/api/Dockerfile) so this image can `pip install -e ../../services/*` —
# requirements.txt's relative paths only resolve if the monorepo's directory
# nesting is preserved inside the image.
FROM python:3.12-slim

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY services/ai-engine /workspace/services/ai-engine
COPY services/connectors /workspace/services/connectors
COPY apps/api /workspace/apps/api

WORKDIR /workspace/apps/api
# --retries/--timeout: the sandboxed build network has shown transient stalls
# against files.pythonhosted.org long enough to trip pip's default read
# timeout on a slow connection — retry instead of failing the whole build.
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt
RUN chmod +x entrypoint.sh

EXPOSE 8000

CMD ["./entrypoint.sh"]
