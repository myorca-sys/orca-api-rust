FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including ffmpeg for video slicing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    unrar \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY apps/api/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and services
COPY apps/api/ .
COPY services/ /app/services/

# Set environment variable for python path
ENV PYTHONPATH="${PYTHONPATH}:/app:/app/services"

# Expose port
EXPOSE 7860

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
