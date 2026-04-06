#!/bin/bash
# Kleinanzeigen Monitor Setup – run once

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UV=/opt/homebrew/bin/uv

echo "==> Installing dependencies with uv..."
cd "$SCRIPT_DIR"
$UV sync

echo "==> Running setup..."
$UV run setup.py
