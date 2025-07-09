FROM python:3.11-slim

# Copy the script and make it executable
COPY install_deps.sh /tmp/install_deps.sh
RUN chmod +x /tmp/install_deps.sh

# Run the script
RUN /tmp/install_deps.sh

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
