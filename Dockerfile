# syntax=docker/dockerfile:1
#
# Hanat training/runtime image. One Dockerfile, two targets selected by build
# args:
#
#   CPU (portable, runs anywhere incl. Apple Silicon):
#     docker build -t hanat:cpu .
#
#   NVIDIA GPU (build/run on a Linux host with the NVIDIA Container Toolkit):
#     docker build -t hanat:gpu \
#       --build-arg BASE_IMAGE=nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04 \
#       --build-arg CUDA_TAG=cu124 .
#
# Both bases are Ubuntu 24.04, so the setup below is identical; only the torch /
# PyG wheels differ. `docker compose` wires both up for you (see compose file).
#
# Python deps are managed with uv (https://docs.astral.sh/uv) into a venv at
# /opt/venv, which is put first on PATH so `python`/`pip` resolve to it.

ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}

# cpu -> CPU wheels ; cu124 -> CUDA 12.4 wheels (pair with the nvidia/cuda base)
ARG CUDA_TAG=cpu
# Pinned to a torch version PyG publishes matching extension wheels for.
ARG TORCH_VERSION=2.5.0

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    STOCKFISH_PATH=/usr/games/stockfish \
    VIRTUAL_ENV=/opt/venv \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:/usr/games:$PATH

# System deps: Python, a C++17 toolchain (to build the native chess engine),
# and Stockfish (for the evaluation bridge). Debian/Ubuntu put the stockfish
# binary at /usr/games/stockfish, which STOCKFISH_PATH/PATH above point at.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-dev \
        build-essential g++ \
        stockfish \
        git ca-certificates \
        cmake \
        qt6-base-dev \
        qt6-svg-dev \
        qt6-5compat-dev \
        qt6-base-dev-tools \
    && rm -rf /var/lib/apt/lists/*

# Build and install Ordo
RUN git clone https://github.com/michiguel/Ordo.git /tmp/ordo \
    && cd /tmp/ordo \
    && make \
    && cp ordo /usr/local/bin/ \
    && rm -rf /tmp/ordo

# Build and install cutechess-cli
RUN git clone https://github.com/cutechess/cutechess.git /tmp/cutechess \
    && cd /tmp/cutechess \
    && cmake -S . -B build \
    && cmake --build build --target cli \
    && cp "$(find build -type f -name cutechess-cli | head -n1)" /usr/local/bin/ \
    && rm -rf /tmp/cutechess

# uv: a single static binary, copied from the official image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create the venv uv installs into (uses the system python3 as the base).
RUN uv venv /opt/venv --python python3

WORKDIR /app

# --- Heavy Python deps first, in their own layer, for build caching -------- #
# torch from the PyTorch wheel index (CPU vs CUDA build), then the optional PyG
# compiled extensions (pyg_lib, scatter, ...). The latter speed up some ops but
# are not required — torch_geometric works without them — so keep the build
# resilient if a wheel is missing for this exact torch/CUDA combo.
RUN uv pip install "torch==${TORCH_VERSION}" \
        --index-url "https://download.pytorch.org/whl/${CUDA_TAG}"
RUN uv pip install pyg_lib torch_scatter torch_sparse torch_cluster torch_spline_conv \
        -f "https://data.pyg.org/whl/torch-${TORCH_VERSION}+${CUDA_TAG}.html" \
 || echo "NOTE: optional PyG extension wheels unavailable for torch-${TORCH_VERSION}+${CUDA_TAG}; torch_geometric will use pure-Python fallbacks."

# --- Project + native chess engine ---------------------------------------- #
COPY . .
# Editable install builds hanat/_chess.cpp into the package and installs the
# pyproject deps (numpy, tqdm, torch_geometric). Then assert the fast backend is
# actually live and the ML stack imports, so a broken image fails the build
# instead of at runtime.
RUN uv pip install -e . --no-build-isolation \
 && python -c "from hanat.board import BACKEND; assert BACKEND=='cpp', BACKEND; print('hanat chess backend:', BACKEND)" \
 && python -c "import torch, torch_geometric as g; print('torch', torch.__version__, '| pyg', g.__version__, '| cuda available:', torch.cuda.is_available())"

CMD ["python", "train.py"]
