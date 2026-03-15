FROM python:3.11-slim as builder

# Define environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# Install system dependencies required for building Python packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies first to cache them
COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && python -c "import tomllib; open('requirements.txt', 'w').write('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" \
    && pip install -r requirements.txt

# Now copy the actual application code
COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini ./alembic.ini
COPY ./run.py ./run.py
COPY ./start.sh ./start.sh

# Stage 2: Runner
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install runtime dependencies ONLY
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy python packages and our code
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /app /app

# Create a non-root user
RUN useradd -m appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose the API port
EXPOSE 8000

# Defaults to running the server
CMD ["python", "run.py"]
