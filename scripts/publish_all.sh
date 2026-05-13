#!/usr/bin/env bash
# Publish all 8 AIGEN SDKs to npm + pypi.
# Run ONCE: npm login (interactive). Then: bash publish_all.sh
#
# What this does:
#   - For each TypeScript SDK: npm install → npm run build → npm publish --access public
#   - For each Python SDK: build wheel + upload to pypi
#
# Pre-requisites you must do ONCE manually (no way to automate without your creds):
#   1. npm login → uses your npmjs.com account
#      Verify: npm whoami → should show your npm username
#   2. Create the @aigen-protocol scope on npm: https://www.npmjs.com/settings/aigen-protocol/orgs
#      (or any other scope you own — adjust package.json names if different)
#   3. For pypi: pip install twine + python -m build
#      Then ~/.pypirc must have your token
#
# Re-run this script anytime to publish new versions.

set -e
cd "$(dirname "$0")/.."

echo "════════════════════════════════════════════════════════════"
echo " AIGEN SDK Publish Script"
echo "════════════════════════════════════════════════════════════"

# --- Pre-flight checks ---
if ! command -v npm >/dev/null; then
  echo "ERROR: npm not found. Install Node first."
  exit 1
fi

NPM_USER=$(npm whoami 2>/dev/null || echo "")
if [ -z "$NPM_USER" ]; then
  echo "ERROR: not logged into npm. Run: npm login"
  exit 1
fi
echo "✓ npm logged in as: $NPM_USER"
echo

# --- TypeScript SDKs (5) ---
TS_SDKS=(
  "integrations/sdk_js"             # @aigen-protocol/sdk
  "integrations/mastra"             # @aigen-protocol/mastra
  "integrations/vercel_ai_sdk"      # @aigen-protocol/vercel-ai-sdk
  "integrations/workers_ai"         # @aigen-protocol/workers-ai
  "integrations/cli"                # @aigen-protocol/cli
)

for sdk in "${TS_SDKS[@]}"; do
  echo "──────────────── $sdk ────────────────"
  if [ ! -d "$sdk" ]; then echo "  SKIP — directory missing"; continue; fi
  pushd "$sdk" > /dev/null

  PKG_NAME=$(node -p "require('./package.json').name")
  PKG_VER=$(node -p "require('./package.json').version")

  # Check if version already published
  PUBLISHED=$(npm view "$PKG_NAME@$PKG_VER" version 2>/dev/null || echo "")
  if [ -n "$PUBLISHED" ]; then
    echo "  ⊘  $PKG_NAME@$PKG_VER already published. Bump version in package.json to publish again."
    popd > /dev/null
    continue
  fi

  # Install + build (skip build for cli — no build step)
  if grep -q '"build"' package.json 2>/dev/null; then
    echo "  → npm install"
    npm install --silent --no-audit --no-fund 2>&1 | tail -3
    echo "  → npm run build"
    npm run build 2>&1 | tail -3
  fi

  echo "  → npm publish $PKG_NAME@$PKG_VER --access public"
  npm publish --access public 2>&1 | tail -3

  popd > /dev/null
  echo
done

# --- Python SDKs (4) ---
PY_SDKS=(
  "integrations/langchain"          # aigen-langchain
  "integrations/crewai"             # aigen-crewai
  "integrations/letta"              # aigen-letta
  "integrations/openai_agents"      # aigen-openai-agents
)

if ! command -v twine >/dev/null; then
  echo "Skipping Python SDKs — install twine first: pip install build twine"
else
  for sdk in "${PY_SDKS[@]}"; do
    echo "──────────────── $sdk ────────────────"
    if [ ! -d "$sdk" ]; then echo "  SKIP — directory missing"; continue; fi
    pushd "$sdk" > /dev/null

    if [ ! -f "pyproject.toml" ] && [ ! -f "setup.py" ]; then
      echo "  ⊘  no pyproject.toml or setup.py"
      popd > /dev/null
      continue
    fi

    rm -rf dist/ build/ *.egg-info
    echo "  → python -m build"
    python -m build --wheel --sdist 2>&1 | tail -3

    echo "  → twine upload dist/*"
    twine upload dist/* 2>&1 | tail -3

    popd > /dev/null
    echo
  done
fi

# --- VS Code extension ---
echo "──────────────── integrations/vscode ────────────────"
if command -v vsce >/dev/null; then
  pushd integrations/vscode > /dev/null
  echo "  → npm install"
  npm install --silent 2>&1 | tail -3
  echo "  → npm run compile"
  npm run compile 2>&1 | tail -3
  echo "  → vsce package"
  vsce package 2>&1 | tail -3
  echo "  → vsce publish (needs PAT — see https://code.visualstudio.com/api/working-with-extensions/publishing-extension#get-a-personal-access-token)"
  vsce publish 2>&1 | tail -3
  popd > /dev/null
else
  echo "  Skipping VS Code — install vsce: npm install -g @vscode/vsce"
fi

echo
echo "════════════════════════════════════════════════════════════"
echo " Done. Verify:"
echo "   npm view @aigen-protocol/sdk"
echo "   pip install aigen-langchain"
echo "════════════════════════════════════════════════════════════"
