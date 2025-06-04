FROM python:3.11-slim

WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p data

# Expose ports
EXPOSE 1234
EXPOSE 9090

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CONFIG_FILE=/app/config.yml

# Run the application
CMD ["python", "main.py"]