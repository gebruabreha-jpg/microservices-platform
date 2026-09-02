"""Event publishing: interface + Kafka and RabbitMQ implementations."""

import json
from abc import ABC, abstractmethod

import pika
from kafka import KafkaProducer


class EventPublisher(ABC):
    @abstractmethod
    async def publish(self, topic: str, event: dict) -> None:
        """Publish an event to a topic/queue."""
        ...


class KafkaEventPublisher(EventPublisher):
    """Kafka implementation.

    Accepts either a live producer or a ``producer_factory`` so a producer that
    could not be created at startup (broker still coming up) is built lazily and
    retried on the next publish.
    """

    def __init__(self, kafka_producer: KafkaProducer = None, circuit_breaker=None, producer_factory=None):
        self._producer = kafka_producer
        self._producer_factory = producer_factory
        self._circuit_breaker = circuit_breaker

    def _get_producer(self):
        if self._producer is None and self._producer_factory is not None:
            self._producer = self._producer_factory()
        if self._producer is None:
            raise RuntimeError("Kafka producer is not available")
        return self._producer

    async def publish(self, topic: str, event: dict) -> None:
        def _send():
            producer = self._get_producer()
            producer.send(topic, event)
            producer.flush(timeout=5)

        if self._circuit_breaker:
            self._circuit_breaker.call(_send)
        else:
            _send()


class RabbitMQEventPublisher(EventPublisher):
    """RabbitMQ implementation."""

    def __init__(self, connection_factory, circuit_breaker=None):
        self._connection_factory = connection_factory
        self._circuit_breaker = circuit_breaker

    async def publish(self, queue: str, event: dict) -> None:
        def _publish():
            connection = self._connection_factory()
            channel = connection.channel()
            # Queues/exchanges are provisioned from rabbitmq/definitions.json at
            # broker boot, so the publisher does not (re)declare them - declaring
            # "notifications" here without its x-dead-letter-exchange argument
            # would raise PRECONDITION_FAILED against the pre-declared queue.
            channel.basic_publish(
                exchange="",
                routing_key=queue,
                body=json.dumps(event),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            connection.close()

        if self._circuit_breaker:
            self._circuit_breaker.call(_publish)
        else:
            _publish()
