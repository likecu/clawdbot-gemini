FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

COPY opencode_requirements.txt .
RUN pip install --no-cache-dir -r opencode_requirements.txt

COPY src/ ./src/
COPY ../opencode_server.py .

ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python", "opencode_server.py"]
