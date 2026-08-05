FROM python:3.12-slim

WORKDIR /app

COPY services/inventory-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/inventory-service/app/ ./app/
COPY services/shared-python-lib/shared ./shared

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]