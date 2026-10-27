FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
VOLUME ["/app/state"]
HEALTHCHECK --interval=60s --timeout=10s --start-period=180s CMD python runner.py --healthcheck
CMD ["python", "runner.py"]
