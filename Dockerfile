FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY server.py .
COPY static ./static
COPY v2 ./v2
RUN mkdir -p outputs

EXPOSE 10000
CMD ["python", "server.py"]
