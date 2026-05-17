FROM python:3.11-slim

WORKDIR /app

# Dipendenze Python
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codice backend
COPY backend/ .

# Frontend statico
COPY frontend/ ./frontend/

# Directory dati (montata come volume in produzione)
RUN mkdir -p /app/data

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
