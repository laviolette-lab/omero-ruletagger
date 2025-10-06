
FROM python:3.11-alpine AS base

# Create vscode user (uid/gid 1000) and install required packages for building wheels
RUN addgroup -g 1000 vscode \
    && adduser -D -u 1000 -G vscode -h /home/vscode -s /bin/sh vscode \
    && apk add --no-cache sudo build-base libffi-dev openssl-dev python3-dev cargo git \
    && printf "vscode ALL=(ALL) NOPASSWD:ALL\n" > /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode

WORKDIR /app
COPY . /app/
RUN chown -R vscode:vscode /app

# Install hatch and build your project artifacts
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
RUN pip3 install --no-cache-dir hatch \
    && sh -c 'if [ -d requirements ]; then find requirements -name "requirement*.txt" -print0 | xargs -0 -r -I{} pip3 install -r "{}"; fi'
USER vscode