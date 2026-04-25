# Multi-stage: pull Python 3.13 from the official slim image and graft it
# onto bitnami/spark:4.0.0 so the worker Python version matches the Jupyter
# driver (also Python 3.13).
FROM python:3.13-slim-bookworm AS py313

FROM bitnamilegacy/spark:4.0.0
USER root

# Copy the Python 3.13 binary + stdlib from the official image
COPY --from=py313 /usr/local/bin/python3.13        /usr/local/bin/python3.13
COPY --from=py313 /usr/local/lib/python3.13        /usr/local/lib/python3.13
COPY --from=py313 /usr/local/lib/libpython3.13.so* /usr/local/lib/
COPY --from=py313 /usr/local/include/python3.13    /usr/local/include/python3.13

RUN ldconfig

USER 1001

# Tell PySpark workers to use Python 3.13
ENV PYSPARK_PYTHON=python3.13
