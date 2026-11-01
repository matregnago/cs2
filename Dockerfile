FROM joedwards32/cs2:latest

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 ca-certificates util-linux \
    && rm -rf /var/lib/apt/lists/*

COPY scripts/ /opt/cs2-mods/
COPY pre.sh /opt/cs2-mods/pre.sh
COPY cfg/ /opt/cs2-mods/cfg/
RUN chmod 755 /opt/cs2-mods/docker-entrypoint.sh

# The wrapper repairs volume ownership, then drops privileges before running CS2.
ENV HOME=/home/steam USER=steam LOGNAME=steam
USER root
ENTRYPOINT ["/opt/cs2-mods/docker-entrypoint.sh"]
CMD ["bash", "/home/steam/entry.sh"]
