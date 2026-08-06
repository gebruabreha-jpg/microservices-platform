#!/bin/bash
kafka-topics --create --topic orders --bootstrap-server kafka:9092 --partitions 3 --replication-factor 1
kafka-topics --create --topic notifications --bootstrap-server kafka:9092 --partitions 3 --replication-factor 1
