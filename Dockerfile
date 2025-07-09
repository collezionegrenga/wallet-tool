FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y gcc build-essential libffi-dev && \
    apt-get clean

# Set working directory
WORKDIR /app

# Copy backend files
COPY backend/ /app

# Install Python packages
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Expose port
EXPOSE 5000

# Run the app
CMD ["python", "app.py"]
