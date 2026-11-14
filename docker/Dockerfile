# Revenant toolchain image: GnuCOBOL 3.x with indexed-file support, plus Python.
# gnucobol4 on Ubuntu 24.04 is built without indexed files and cannot compile the exhibit.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      gnucobol3 \
      python3 \
      python3-pip \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Python MCP SDK for the stdio server that Kiro launches.
ARG MCP_VERSION=2.3.0
RUN pip install --no-cache-dir --break-system-packages "mcp${MCP_VERSION:+==$MCP_VERSION}"

WORKDIR /work
