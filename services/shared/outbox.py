"""
Transactional outbox.

A service that must publish an event when it writes to its database cannot do
both atomically against two systems. Instead it writes the event into an
``*_outbox`` table *in the same DB transaction* as the business row, and a
background poller relays unpublished rows to the broker and marks them sent.

If the broker is down the rows simply stay unpublished and are retried; the
business write is never lost, and the event is never published without the
write having committed.
"""

import asyncio
import json
import threading


def enqueue_event(cursor, table: str, topic: str, payload: dict) -> None:
    """Insert an outbox row using an already-open cursor (caller commits).

    Must be called on the same connection/transaction as the business insert so
    the two either commit together or roll back together.
    """
    cursor.execute(
        f"INSERT INTO {table} (topic, payload) VALUES (%s, %s::jsonb)",
        (topic, json.dumps(payload)),
    )


class OutboxPoller:
    """Relays rows from an outbox table to an EventPublisher. Run ``run`` in a daemon thread."""

    def __init__(
        self,
        db_pool,
        publisher,
        logger,
        *,
        table: str,
        poll_interval: float = 2.0,
        batch_size: int = 100,
    ):
        self._db_pool = db_pool
        self._publisher = publisher
        self._logger = logger
        self._table = table
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._stop = threading.Event()
        self._loop = None

    def stop(self) -> None:
        """Signal the poll loop to exit (called on application shutdown)."""
        self._stop.set()

    def run(self) -> None:
        """Blocking poll loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._logger.info("Outbox poller started", table=self._table)
        while not self._stop.is_set():
            try:
                # Keep draining while a backlog exists, otherwise sleep.
                if self._drain_once() == self._batch_size:
                    continue
            except Exception as e:
                self._logger.error("Outbox poll failed", error=str(e), table=self._table)
            self._stop.wait(self._poll_interval)
        self._logger.info("Outbox poller stopped", table=self._table)

    def _drain_once(self) -> int:
        if not self._db_pool:
            return 0
        conn = self._db_pool.getconn()
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT id, topic, payload FROM {self._table}
                WHERE published_at IS NULL
                ORDER BY id
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (self._batch_size,),
            )
            rows = cur.fetchall()
            for row_id, topic, payload in rows:
                event = payload if isinstance(payload, dict) else json.loads(payload)
                self._loop.run_until_complete(self._publisher.publish(topic, event))
                cur.execute(
                    f"UPDATE {self._table} SET published_at = NOW() WHERE id = %s",
                    (row_id,),
                )
            conn.commit()
            if rows:
                self._logger.info("Outbox relayed", count=len(rows), table=self._table)
            return len(rows)
        except Exception:
            conn.rollback()
            raise
        finally:
            if cur is not None:
                cur.close()
            self._db_pool.putconn(conn)
