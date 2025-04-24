#!/bin/bash

python3 -m venv venv
source ./venv/bin/activate
pip install \
  opentelemetry-exporter-otlp \
  opentelemetry-exporter-jaeger \
  opentelemetry-exporter-otlp-proto-grpc \
  opentelemetry-exporter-otlp-proto-http \
  opentelemetry-sdk \
  opentelemetry-api \
  opentelemetry-exporter-jaeger-proto-grpc
