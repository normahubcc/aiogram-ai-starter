# Build and runtime stage
FROM python:3.12-slim

# Set environment variables for clean container execution
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies (curl for healthchecks, ca-certificates for TLS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates=20240203 \
    curl=7.88.1-10+deb12u8 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root group and user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -d /app -M appuser

WORKDIR /app

# Copy dependency definition and install packages
COPY pyproject.toml /app/
RUN pip install --no-cache-dir .

# Copy application code
COPY bot/ /app/bot/

# Ensure non-root ownership
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Healthcheck to verify process health
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import bot" || exit 1

# Launch application
CMD ["python", "-m", "bot.main"]
