# Use official Python 3.11 slim image
FROM python:3.11-slim

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies required to build some Python packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       gcc \
       libffi-dev \
       libssl-dev \
       git \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install first to leverage Docker cache
COPY requirements.txt /app/

# Upgrade pip and install dependencies
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . /app/

# Create a non-root user and give ownership of the app directory
RUN groupadd -r app && useradd -r -g app app \
    && chown -R app:app /app
USER app

# Expose port (matches uvicorn command in README)
EXPOSE 8000

# Default command to run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
