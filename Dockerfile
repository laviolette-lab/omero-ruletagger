FROM python:3.11-slim AS base

# create non-root user (uid 1000). adduser exists in debian-slim.
RUN adduser --uid 1000 --disabled-password --gecos "" vscode

WORKDIR /app
COPY . /app/
RUN chown -R vscode:vscode /app

# Install hatch and build
RUN pip3 install --no-cache-dir hatch \
    && hatch run build

FROM base AS hatch
ENV HATCH_ENV=default
ENTRYPOINT ["hatch", "run"]

FROM base AS prod
RUN pip3 install --no-cache-dir /app/dist/*.whl
USER vscode

FROM base AS dev

ENV PATH=/home/vscode/.local/bin:$PATH
RUN getent group 1000 >/dev/null 2>&1 || groupadd --gid 1000 vscode \
    && id -u vscode >/dev/null 2>&1 || useradd --uid 1000 --gid 1000 -m -d /home/vscode -s /bin/bash vscode \
    && apt-get update && apt-get install -y sudo \
    && usermod -aG sudo vscode \
    && printf "vscode ALL=(ALL) NOPASSWD:ALL\n" > /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode \
    && pip3 install --no-cache-dir hatch \
    && if [ -d requirements ]; then find requirements -name "requirement*.txt" -print0 | xargs -0 -r -I{} pip3 install -r "{}"; fi
USER vscode