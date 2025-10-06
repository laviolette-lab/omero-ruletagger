# ARG OMEROPY_VERSION=1.1.5-python3.10
# FROM ghcr.io/lavlabinfrastructure/lavlab-omeropy-container:$OMEROPY_VERSION as base
FROM python:3.11.13-bookworm
RUN groupadd --gid 1000 vscode \
    && useradd --uid 1000 --gid 1000 -m vscode \
    && apt-get update && apt-get install -y sudo \
    && usermod -aG sudo vscode \
    && printf "vscode ALL=(ALL) NOPASSWD:ALL\n" > /etc/sudoers.d/vscode \
    &&  chmod 0440 /etc/sudoers.d/vscode

WORKDIR /app
COPY . /app/
RUN chown -R vscode /app

RUN pip3 install hatch
RUN hatch run build

FROM base AS hatch
ENV HATCH_ENV=default
ENTRYPOINT ["hatch", "run"]

FROM base AS prod
RUN pip3 install /app/dist/*.whl
USER vscode

FROM base as dev
ENV PATH ~/.local/bin:$PATH
RUN pip3 install hatch 
RUN find requirements -name 'requirement*.txt' | while read requirement; do \
    pip3 install -r "$requirement"; \
    done
USER vscode
