Docker Compose setup:

Servers:

1 physical server — your Windows PC
~18 containers on that single server (PostgreSQL, Redis, NGINX, Kafka, Zookeeper, Kafka REST, RabbitMQ, Prometheus, Grafana, Loki, Tempo, OTel Collector, Node Exporter, cAdvisor, Kafka UI, Redis Insight, PgAdmin, Mailhog, plus 4 app services)
Load balancing applicability:

Yes, but limited. Since everything runs on one Docker host, load balancing works at the container level, not across physical machines.

Docker Compose round-robin: If you scale a service (docker compose up -d --scale order-service=3), Docker's internal DNS load balances across replicas
NGINX upstream blocks: Your current nginx.conf already has upstream definitions (upstream order-service { server order-service:8080; }). If you deploy multiple replicas, NGINX will load balance across them
No cross-machine LB: You'd need Docker Swarm or Kubernetes for true distributed load balancing across multiple PCs/servers