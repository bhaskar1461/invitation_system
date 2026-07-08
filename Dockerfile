# Use the official Python 3.11-slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Set working directory
WORKDIR /app

# Install system dependencies (compiler tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application assets
COPY . .

# Expose server port
EXPOSE 8000

# Initialize the database and launch Gunicorn
CMD ["sh", "-c", "python db_init.py && gunicorn --bind 0.0.0.0:8000 app:app"]
