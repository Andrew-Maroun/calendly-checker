FROM selenium/standalone-chrome:latest

USER root

# Install Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages

# Copy app
COPY app.py .

# Change ownership to seluser (existing user in selenium image)
RUN chown -R seluser:seluser /app

# Switch to non-root user
USER seluser

EXPOSE 10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app", "--timeout", "120"]
