FROM python:3.12-slim

WORKDIR /app

# Thin layer: no droid CLI or browsers here. Droids run on the Droid Computer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
