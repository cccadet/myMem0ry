FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ripgrep && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY bin/ bin/

RUN uv sync --no-dev --frozen

RUN uv run python -c "
import spacy
try:
    spacy.load('pt_core_news_lg')
except OSError:
    spacy.cli.download('pt_core_news_lg')
"

ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=49374
ENV CONVERSATIONS_DIR=/data/conversations
ENV DB_PATH=/data/memories.db
ENV VECTOR_DB_PATH=/data/conversations/.vec.db

VOLUME /data

EXPOSE 49374

CMD ["uv", "run", "mymem0ry-mcp"]
