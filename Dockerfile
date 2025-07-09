FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Copy only backend folder contents
COPY backend/ /app

# Install Python packages
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Expose backend port
EXPOSE 5000

# Run the Flask app
CMD ["python", "app.py"]
