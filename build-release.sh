#!/bin/bash
# Script to build and package the Group Photo Sorter app for Nextcloud distribution

set -e

APP_ID="group_photo_sorter"
BUILD_DIR="build"
DIST_DIR="dist"
TARGET_DIR="${BUILD_DIR}/${APP_ID}"

echo "=== Starting release build for ${APP_ID} ==="

# 1. Clean previous builds
echo "Cleaning old build and dist directories..."
rm -rf "${BUILD_DIR}"
rm -rf "${DIST_DIR}"
mkdir -p "${BUILD_DIR}"
mkdir -p "${DIST_DIR}"

# 2. Build Svelte frontend
echo "Building frontend assets..."
cd frontend
npm install
npm run build:nextcloud
cd ..

# 3. Create app package structure
echo "Preparing release files..."
mkdir -p "${TARGET_DIR}"

# Copy production folders
cp -r appinfo "${TARGET_DIR}/"
cp -r bin "${TARGET_DIR}/"
cp -r css "${TARGET_DIR}/"
cp -r js "${TARGET_DIR}/"
cp -r lib "${TARGET_DIR}/"
cp -r templates "${TARGET_DIR}/"
[ -d img ] && cp -r img "${TARGET_DIR}/"

# Copy root metadata
cp README.md "${TARGET_DIR}/"
cp LICENSE "${TARGET_DIR}/"

# Clean up dev-only files inside copied folders (if any)
find "${TARGET_DIR}" -name ".git*" -delete
find "${TARGET_DIR}" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# 4. Perform sanity checks
echo "Running sanity checks..."
if [ ! -f "${TARGET_DIR}/appinfo/info.xml" ]; then
    echo "ERROR: info.xml is missing from the package!"
    exit 1
fi

if [ ! -f "${TARGET_DIR}/js/group_photo_sorter.js" ]; then
    echo "ERROR: Compiled JavaScript asset is missing!"
    exit 1
fi

# 5. Compress
TARBALL="${DIST_DIR}/${APP_ID}.tar.gz"
echo "Packaging into ${TARBALL}..."
cd "${BUILD_DIR}"
tar -czf "../${TARBALL}" "${APP_ID}"
cd ..

echo "Cleaning up temporary build folder..."
rm -rf "${BUILD_DIR}"

echo "=== Build Complete ==="
echo "Tarball created at: ${TARBALL}"
echo ""
echo "To publish on the Nextcloud App Store, you MUST sign this package."
echo "Follow these steps to sign the archive:"
echo "  1. If you don't have a private key, generate one:"
echo "     openssl genrsa -out group_photo_sorter.key 4096"
echo "  2. Sign the archive (runs occ internally, or manually signs it):"
echo "     php /path/to/nextcloud/occ app:sign --privateKey=group_photo_sorter.key --archive=${TARBALL}"
echo "     (This will create ${TARBALL}.sig)"
echo "  3. When uploading the release to apps.nextcloud.com, register your public key and provide the signature file."
echo ""
