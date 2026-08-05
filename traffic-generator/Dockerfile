FROM python:3.12-slim

WORKDIR /traffic-generator

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY locustfile.py .
COPY scenarios/ ./scenarios/

EXPOSE 8089

CMD ["locust", "-f", "locustfile.py", "--host", "http://nginx", "--web-port", "8089", "--bind-host", "0.0.0.0"]