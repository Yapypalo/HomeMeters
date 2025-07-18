FROM python:3.12-slim

WORKDIR /homemeters

# Устанавливаем зависимости для Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libnss3 \
    libglib2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    libdbus-glib-1-2 \
    libxtst6 \
    libxss1 \
    libasound2 \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем Playwright и загружаем движок Chromium
RUN playwright install --with-deps chromium

COPY . .

CMD [ "bash"]
