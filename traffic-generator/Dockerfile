FROM python:3.12-slim

WORKDIR /traffic-generator

COPY services/traffic-generator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/traffic-generator/locustfile.py .
COPY services/traffic-generator/scenarios/ ./scenarios/

EXPOSE 8089

CMD ["locust", "-f", "locustfile.py", "--host", "http://nginx", "--web-port", "8089", "--bind-host", "0.0.0.0"]