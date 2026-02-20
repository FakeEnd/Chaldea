# Use the official Playwright image which includes Python and browsers
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Install Playwright browsers (ensure they are available)
RUN playwright install chromium

# Command to run the bot
CMD ["python", "bot.py"]
