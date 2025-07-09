FROM python:3.11-slim

# Install system dependencies
RUN apt-get update &amp;&amp; apt-get install -y gcc build-essential libffi-dev --no-install-recommends &amp;&amp; apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements file
COPY backend/requirements.txt /app/requirements.txt

# Install Python packages
RUN pip install --upgrade pip &amp;&amp; \
    pip install --no-cache-dir -r requirements.txt

# Copy backend files
COPY backend/ /app

# Command to run the Flask application
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"]
