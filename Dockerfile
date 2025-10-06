FROM python:3.11-slim AS base

RUN groupadd --gid 1000 vscode \
    && useradd --uid 1000 --gid 1000 -m -d /home/vscode -s /bin/bash vscode

WORKDIR /app
COPY . /app/
RUN chown -R vscode:vscode /app

RUN pip3 install --no-cache-dir hatch

FROM base AS hatch
ENV HATCH_ENV=default
ENTRYPOINT ["hatch", "run"]

FROM base AS prod
RUN hatch run build && pip3 install --no-cache-dir /app/dist/*.whl 
USER vscode

FROM base AS dev
ENV PATH=/home/vscode/.local/bin:$PATH

RUN apt-get update && apt-get install -y sudo \
    && usermod -aG sudo vscode \
    && printf "vscode ALL=(ALL) NOPASSWD:ALL\n" > /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode \
    && pip3 install --no-cache-dir hatch \
    && if [ -d requirements ]; then find requirements -name "requirement*.txt" -print0 | xargs -0 -r -I{} pip3 install -r "{}"; fi
USER vscode
