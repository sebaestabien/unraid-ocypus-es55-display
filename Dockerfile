FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pyserial pillow psutil
COPY *.py /app/
EXPOSE 8799
CMD ["python3", "-u", "/app/es55_driver.py"]
