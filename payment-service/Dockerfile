FROM python:3.12-slim

WORKDIR /app

COPY payment-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY payment-service/app/ ./app/
COPY shared-python-lib/shared ./shared

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]