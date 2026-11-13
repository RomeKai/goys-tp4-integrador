# Root-cause explanation service for Act 3. Built once with internet, then shipped inside the offline tar.
FROM python:3.12.7-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py page.py replay.py .

# The service only talks HTTP to Prometheus, Ollama and Grafana; it does not need root.
USER nobody
EXPOSE 8085
CMD ["python", "main.py"]
