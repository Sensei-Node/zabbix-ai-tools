FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from parent
COPY docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy logic from parent
COPY genai_engine.py /app/genai_engine.py
COPY openai_engine.py /app/openai_engine.py
COPY siem_fetching.py /app/siem_fetching.py
COPY mcp_client.py /app/mcp_client.py

# Copy app code
COPY docker/* .

RUN mkdir -p /app/outputs /app/data

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
