# Anomaly detector for Act 2. Built once with internet, then shipped inside the offline tar.
FROM python:3.12.7-slim-bookworm

# One math thread is plenty for ~30 rows x a handful of columns and keeps CPU usage near zero.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py .

# The detector only needs network access to Prometheus, not root.
USER nobody
EXPOSE 8000
CMD ["python", "main.py"]
