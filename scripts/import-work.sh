#!/bin/bash

set -e

# Folder containing the extracted ChatGPT Work project.
WORK="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Documents/ChatGPT-Work/Discogs-Intelligence-Platform/latest/dip/"

# Automatically identify the repository from the location of this script.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

echo
echo "======================================================"
echo " Discogs Intelligence Platform - Work Import"
echo "======================================================"
echo
echo "Work output:"
echo "  $WORK"
echo
echo "Git repository:"
echo "  $REPO"
echo

# Check the extracted Work output exists.
if [ ! -d "$WORK" ]; then
    echo "❌ Work folder not found:"
    echo "   $WORK"
    echo
    echo "Extract the Work ZIP into the 'latest' folder first."
    exit 1
fi

# Check this script is inside the Git repository.
if [ ! -d "$REPO/.git" ]; then
    echo "❌ Git repository not found:"
    echo "   $REPO"
    echo
    echo "The script should be located at:"
    echo "   <repository>/scripts/import-work.sh"
    exit 1
fi

echo "Preview of files to be synchronised:"
echo

rsync -avn \
    --exclude='.git/' \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='.pytest_cache/' \
    --exclude='*.egg-info/' \
    --exclude='.DS_Store' \
    "$WORK" \
    "$REPO"

echo
read -r -p "Continue? (y/N): " CONFIRM

case "$CONFIRM" in
    y|Y|yes|YES)
        ;;
    *)
        echo
        echo "Import cancelled."
        exit 0
        ;;
esac

echo
echo "Synchronising Work output..."

rsync -av \
    --exclude='.git/' \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='.pytest_cache/' \
    --exclude='*.egg-info/' \
    --exclude='.DS_Store' \
    "$WORK" \
    "$REPO"

cd "$REPO"

echo
echo "======================================================"
echo " Git Status"
echo "======================================================"
echo

git status --short

echo
echo "======================================================"
echo " Running Tests"
echo "======================================================"
echo

python3 -m pytest

echo
echo "======================================================"
echo " Import Complete"
echo "======================================================"
echo
echo "Review the changes before committing:"
echo
echo "  git diff"
echo "  git status"
echo