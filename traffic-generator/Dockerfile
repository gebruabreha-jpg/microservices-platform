FROM python:3.12-slim

WORKDIR /traffic-generator

COPY traffic-generator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY traffic-generator/locustfile.py traffic-generator/locust.conf ./

RUN mkdir -p results

EXPOSE 8089

# locust.conf supplies the defaults; compose overrides users/spawn-rate/run-time
# via LOCUST_* env vars.
CMD ["locust", "--web-host", "0.0.0.0"]
