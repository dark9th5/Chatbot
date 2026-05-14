FROM python:3.11-slim

WORKDIR /app

# Install build dependencies then runtime deps
COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "chatbot_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
