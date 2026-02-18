#!/bin/bash

set -e
set -o pipefail

# --------- Configuration ---------
PYTHON_BIN=$(which python3)
NUM_CORES=$(nproc) # For parallel build
LLAMA_CPP_REPO="https://github.com/ggerganov/llama.cpp"
LLAMA_CPP_DIR="llama.cpp"
BUILD_DIR="build"
VENV_DIR="llama_env"
# ---------------------------------

echo "Starting build of llama-cpp-python with GPU and cuBLAS support in a virtual environment..."

# Step 1: Install required system dependencies
echo "Installing system dependencies..."
sudo apt update
sudo apt install -y build-essential cmake git libopenblas-dev liblapack-dev \
  python3-dev python3-venv

# Step 2: Check CUDA
if ! command -v nvcc &>/dev/null; then
  echo "CUDA compiler (nvcc) not found. Please install CUDA."
  exit 1
fi
echo "CUDA detected at $(which nvcc)"

# Step 3: Create virtual environment
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating Python virtual environment at $VENV_DIR..."
  $PYTHON_BIN -m venv $VENV_DIR
else
  echo "Virtual environment already exists."
fi

# Activate virtual environment
source $VENV_DIR/bin/activate

# Upgrade pip and install wheel/setuptools
pip install --upgrade pip setuptools wheel

# Step 4: Clone llama.cpp if not already present
if [ ! -d "$LLAMA_CPP_DIR" ]; then
  echo "Cloning llama.cpp repository..."
  git clone --recurse-submodules $LLAMA_CPP_REPO
else
  echo "Repository already exists. Pulling latest changes..."
  cd $LLAMA_CPP_DIR
  git pull
  git submodule update --init --recursive
  cd ..
fi

# Step 5: Build llama.cpp with GPU support
echo "Building llama.cpp with GPU and cuBLAS..."
cd $LLAMA_CPP_DIR
mkdir -p $BUILD_DIR
cd $BUILD_DIR

cmake .. \
  -DGGML_CUDA=ON \
  -DGGML_CUBLAS=ON \
  -DCMAKE_BUILD_TYPE=Release

make -j$NUM_CORES

cd ../..

# Step 6: Install llama-cpp-python in virtual environment
echo "Installing llama-cpp-python from source in virtual environment..."
pip install --no-binary :all: llama-cpp-python

echo "Build and installation complete!"
echo "Virtual environment located at: $VENV_DIR"
echo "To activate it, run: source $VENV_DIR/bin/activate"
echo "You can test with:"
echo "python -c 'import llama_cpp; print(llama_cpp.__version__)'"
