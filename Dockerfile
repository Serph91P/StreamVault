# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first (for caching)
COPY requirements.txt ./

# Install the required packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port FastAPI is running on
EXPOSE 7000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7000"]
