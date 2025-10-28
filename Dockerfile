FROM python:3.12-slim

RUN apt-get update -qq && \
    apt-get install -y -qq mailutils cron socat && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN pip install -e .

COPY update_epg.sh /usr/local/bin/update_epg.sh
RUN chmod +x /usr/local/bin/update_epg.sh

ENTRYPOINT ["/usr/local/bin/update_epg.sh"]
