# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.209.6/containers/python-3/.devcontainer/base.Dockerfile

# [Choice] Python version (use -bullseye variants on local arm64/Apple Silicon): 3, 3.10, 3.9, 3.8, 3.7, 3.6, 3-bullseye, 3.10-bullseye, 3.9-bullseye, 3.8-bullseye, 3.7-bullseye, 3.6-bullseye, 3-buster, 3.10-buster, 3.9-buster, 3.8-buster, 3.7-buster, 3.6-buster
ARG VARIANT="3.10-bullseye"
FROM mcr.microsoft.com/vscode/devcontainers/python:0-${VARIANT}

# [Choice] Node.js version: none, lts/*, 16, 14, 12, 10
ARG NODE_VERSION="none"
RUN if [ "${NODE_VERSION}" != "none" ]; then su vscode -c "umask 0002 && . /usr/local/share/nvm/nvm.sh && nvm install ${NODE_VERSION} 2>&1"; fi

# [Optional] If your pip requirements rarely change, uncomment this section to add them to the image.
# COPY requirements.txt /tmp/pip-tmp/
# RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
#    && rm -rf /tmp/pip-tmp

RUN su vscode -c "curl -sSL https://install.python-poetry.org | python3 - -yf" 2>&1 \
    && /home/vscode/.local/bin/poetry completions bash > /etc/bash_completion.d/poetry \
    && su vscode -c "pip3 install --user poetry-exec-plugin" 2>&1

RUN mkdir -p /workspaces/co-stock-status \
    && chown vscode:vscode /workspaces/co-stock-status

COPY pyproject.toml /workspaces/co-stock-status/pyproject.toml

# trick poetry, so that the venv created will be associated with the host mounted source later
RUN su vscode -c "cd /workspaces/co-stock-status && /home/vscode/.local/bin/poetry install" 2>&1 \
    && rm -rf /workspaces/co-stock-status

RUN curl -sSL https://cli.openfaas.com | sudo -E sh \
    && su vscode -c "mkdir -p ~/.{kube,config/helm}"

RUN VERSION=$(curl -s https://github.com/mikefarah/yq/releases/latest | awk -F\" '{gsub(/.*\//, "", $2); print $2}') \
    && curl -Lo /usr/local/bin/yq https://github.com/mikefarah/yq/releases/download/${VERSION}/yq_linux_amd64 \
    && chmod +x /usr/local/bin/yq

# [Optional] Uncomment this section to install additional OS packages.
# RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
#     && apt-get -y install --no-install-recommends <your-package-list-here>

# [Optional] Uncomment this line to install global node packages.
# RUN su vscode -c "source /usr/local/share/nvm/nvm.sh && npm install -g <your-package-here>" 2>&1

RUN rm -rf /etc/localtime &> /dev/null || true
