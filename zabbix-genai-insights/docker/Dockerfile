FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from parent
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy logic from parent
COPY dsk_engine.py /app/dsk_engine.py
COPY genai_engine.py /app/genai_engine.py
COPY openai_engine.py /app/openai_engine.py
COPY siem_fetching.py /app/siem_fetching.py
COPY mcp_client.py /app/mcp_client.py
COPY memory_manager.py /app/memory_manager.py

# Copy app code
COPY docker/* .
RUN rm Dockerfile *.txt

RUN mkdir -p /app/outputs /app/data

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
