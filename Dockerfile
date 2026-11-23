FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    SERIAL_PORT="/dev/ttyACM0" \
    SCREEN_WIDTH="960" \
    SCREEN_HEIGHT="480" \
    SCREEN_BRIGHTNESS="80" \
    SCREEN_ROTATION="0" \
    REFRESH_INTERVAL="1" \
    WALLPAPER_DIR="/config/wallpapers" \
    SLIDESHOW_INTERVAL="600" \
    BG_DIM="35"

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    lm-sensors \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pyserial pillow psutil

WORKDIR /app
COPY es55_driver.py /app/es55_driver.py

CMD ["python", "/app/es55_driver.py"]
