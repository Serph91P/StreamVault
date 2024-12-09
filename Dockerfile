# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first (for caching)
COPY requirements.txt ./

# Install the required packages
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get remove -y gcc python3-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy the rest of the application code
COPY . .

# Expose the port FastAPI is running on
EXPOSE 7000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7000"]

