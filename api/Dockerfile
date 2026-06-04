FROM python:3.13-slim

WORKDIR /app
RUN pip install --no-cache-dir bentoml==1.4.32 prometheus-client
COPY api /app/api
ENV PYTHONPATH=/app
EXPOSE 3000
CMD ["bentoml", "serve", "api.service:AviationDisruptionService", "--host", "0.0.0.0", "--port", "3000"]
