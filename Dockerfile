FROM python:3.11-slim AS base

RUN groupadd --gid 1000 coder \
    && useradd --uid 1000 --gid 1000 -m -d /home/coder -s /bin/bash coder

WORKDIR /app
COPY . /app/
RUN chown -R coder:coder /app

RUN pip3 install --no-cache-dir hatch
ENV HATCH_ENV=default

FROM base AS hatch
ENTRYPOINT ["hatch", "run"]

FROM base AS prod
RUN hatch run build && pip3 install --no-cache-dir /app/dist/*.whl 
USER coder

FROM base AS dev
ENV PATH=/home/coder/.local/bin:$PATH

RUN apt-get update && apt-get install -y sudo \
    && usermod -aG sudo coder \
    && printf "coder ALL=(ALL) NOPASSWD:ALL\n" > /etc/sudoers.d/coder \
    && chmod 0440 /etc/sudoers.d/coder \
    && pip3 install --no-cache-dir hatch \
    && if [ -d requirements ]; then find requirements -name "requirement*.txt" -print0 | xargs -0 -r -I{} pip3 install -r "{}"; fi
USER coder
