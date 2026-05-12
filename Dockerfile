FROM ghcr.io/astral-sh/uv:debian

ARG VERSION=Undefined

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV VERSION=${VERSION}

RUN uv init --no-workspace
RUN uv add \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    wyoming \
    zeroconf \
    pocket-tts 

COPY src .

EXPOSE 10300
CMD ["uv", "run", "python", "wyoming_server.py"]