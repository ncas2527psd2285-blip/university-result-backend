FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    wget curl unzip chromium chromium-driver

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER=/usr/bin/chromedriver

EXPOSE 5000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--timeout", "120"]