# Variables
PYTHON := python
PIP := $(PYTHON) -m pip
PYINSTALLER := pyinstaller

# Directories
ASSETS_DIR := assets
SRC_DIR := src
# (or ReWare.ico for Windows)
ICON := $(ASSETS_DIR)/ReWare.png
DIST_DIR := dist
BUILD_DIR := build

# Check if the icon exists, otherwise PyInstaller will throw an error
ICON_FLAG = $(shell if [ -f $(ICON) ]; then echo "--icon=$(ICON)"; fi)

.PHONY: all install build build-server build-client clean

# Default target
all: install build

# Install dependencies
install:
	$(PIP) install --upgrade pip
	$(PIP) install colorama keyboard mouse mss pillow pyinstaller websockets

# Build both applications
build: build-server build-client

# Build the Server/GUI (Windowed, no console popup)
build-server:
	@echo "Building Server/GUI..."
	$(PYINSTALLER) --noconfirm --onefile --windowed $(ICON_FLAG) --name "ReWare GUI" $(SRC_DIR)/main.py

# Build the Client (Console app)
build-client:
	@echo "Building Client..."
	$(PYINSTALLER) --noconfirm --onefile --console $(ICON_FLAG) --name "ReWare Client" $(SRC_DIR)/client.py

# Clean up build artifacts
clean:
	@echo "Cleaning up..."
	rm -rf $(DIST_DIR) $(BUILD_DIR) *.spec  # Adjust commands for Windows
	rm -rf __pycache__
