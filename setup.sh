#!/usr/bin/env bash
#
# Hanat setup for a vast.ai (or any Ubuntu CUDA) GPU box.
#
# Assumes the base image already provides: CUDA + NVIDIA driver, Python + pip,
# PyTorch (GPU build), and JupyterLab. This script layers on everything else the
# project needs: a C++ toolchain for the native engine, Stockfish, cutechess-cli,
# Ordo, torch_geometric, and the editable install of the package itself.
#
# Usage (from the repo root):
#   bash setup.sh
#
set -euo pipefail

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    SUDO="sudo"
fi

echo "==> [1/6] Installing system dependencies (apt) ..."
export DEBIAN_FRONTEND=noninteractive
$SUDO apt-get update
$SUDO apt-get install -y --no-install-recommends \
    python3-dev \
    build-essential g++ \
    stockfish \
    git ca-certificates \
    cmake \
    qt6-base-dev \
    qt6-svg-dev \
    qt6-5compat-dev \
    qt6-base-dev-tools

echo "==> [2/6] Installing Ordo ..."
if command -v ordo >/dev/null 2>&1; then
    echo "    ordo already on PATH ($(command -v ordo)); skipping."
else
    tmp_ordo="$(mktemp -d)"
    git clone --depth 1 https://github.com/michiguel/Ordo.git "$tmp_ordo"
    make -C "$tmp_ordo"
    $SUDO cp "$tmp_ordo/ordo" /usr/local/bin/
    rm -rf "$tmp_ordo"
fi

echo "==> [3/6] Installing cutechess-cli ..."
if command -v cutechess-cli >/dev/null 2>&1; then
    echo "    cutechess-cli already on PATH ($(command -v cutechess-cli)); skipping."
else
    tmp_cc="$(mktemp -d)"
    git clone --depth 1 https://github.com/cutechess/cutechess.git "$tmp_cc"
    cmake -S "$tmp_cc" -B "$tmp_cc/build"
    cmake --build "$tmp_cc/build" --target cli
    $SUDO cp "$(find "$tmp_cc/build" -type f -name cutechess-cli | head -n1)" /usr/local/bin/
    rm -rf "$tmp_cc"
fi

echo "==> [4/6] Installing PyG extension wheels for the existing torch ..."
# Use the base image's torch as-is; just match the optional PyG extension wheels
# to its version + CUDA tag. These speed up some ops but torch_geometric works
# without them, so this step is best-effort.
TORCH_VERSION="$(python -c 'import torch; print(torch.__version__.split("+")[0])')"
CUDA_TAG="$(python -c 'import torch; v=torch.version.cuda; print("cu"+v.replace(".","")) if v else print("cpu")')"
echo "    detected torch ${TORCH_VERSION} (${CUDA_TAG})"
pip install pyg_lib torch_scatter torch_sparse torch_cluster torch_spline_conv \
        -f "https://data.pyg.org/whl/torch-${TORCH_VERSION}+${CUDA_TAG}.html" \
 || echo "NOTE: optional PyG extension wheels unavailable for torch-${TORCH_VERSION}+${CUDA_TAG}; torch_geometric will use pure-Python fallbacks."
pip install torch_geometric

echo "==> [5/6] Installing the hanat package (builds the native C++ engine) ..."
pip install -e . --no-build-isolation

echo "==> [6/6] Verifying installation ..."
python -c "from hanat.board import BACKEND; assert BACKEND=='cpp', BACKEND; print('hanat chess backend:', BACKEND)"
python -c "import torch, torch_geometric as g; print('torch', torch.__version__, '| pyg', g.__version__, '| cuda available:', torch.cuda.is_available())"
for bin in stockfish cutechess-cli ordo; do
    if command -v "$bin" >/dev/null 2>&1; then
        echo "    found $bin -> $(command -v "$bin")"
    else
        echo "    WARNING: $bin not found on PATH"
    fi
done

echo
echo "Setup complete. Before running find_elo, export the Stockfish path:"
echo "    export STOCKFISH_PATH=\$(command -v stockfish)"
