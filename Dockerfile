FROM python:3.11-slim AS base

RUN groupadd --gid 1000 coder \
    && useradd --uid 1000 --gid 1000 -m -d /home/coder -s /bin/bash coder

WORKDIR /app
COPY . /app/
RUN chown -R coder:coder /app

RUN pip3 install --no-cache-dir hatch
ENV HATCH_ENV=default

FROM base AS dev
ENV PATH=/home/coder/.local/bin:$PATH

RUN apt-get update && apt-get install -y sudo \
    && usermod -aG sudo coder \
    && printf "coder ALL=(ALL) NOPASSWD:ALL\n" > /etc/sudoers.d/coder \
    && chmod 0440 /etc/sudoers.d/coder \
    && if [ -d requirements ]; then find requirements -name "requirement*.txt" -print0 | xargs -0 -r -I{} pip3 install -r "{}"; fi
USER coder

FROM base AS hatch
ENTRYPOINT ["hatch", "run"]

FROM base AS prod
RUN hatch env run build \
    && arch="$(uname -m)" \
    && if [ "$arch" = "x86_64" ]; then \
    url="https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20240202/zeroc_ice-3.6.5-cp311-cp311-manylinux_2_28_x86_64.whl"; \
    elif [ "$arch" = "aarch64" ] || [ "$arch" = "arm64" ]; then \
    url="https://github.com/glencoesoftware/zeroc-ice-py-linux-aarch64/releases/download/20240620/zeroc_ice-3.6.5-cp311-cp311-manylinux_2_28_aarch64.whl"; \
    else \
    echo "Unsupported architecture: $arch" >&2; exit 1; \
    fi \
    && echo "Installing zeroc-ice wheel for arch=$arch: $url" \
    && pip3 install --no-cache-dir "$url" \
    && pip3 install --no-cache-dir /app/dist/*.whl
USER coder
