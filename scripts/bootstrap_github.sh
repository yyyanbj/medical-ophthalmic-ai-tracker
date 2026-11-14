#!/usr/bin/env bash
# Create the user's public repository and enable Pages via the authenticated gh CLI.
set -euo pipefail
OWNER="${1:-yyyanbj}"
REPO="medical-ophthalmic-ai-tracker"
command -v gh >/dev/null || { echo "Please install GitHub CLI: https://cli.github.com/"; exit 1; }
command -v git >/dev/null || { echo "Please install git first."; exit 1; }
gh auth status >/dev/null
cd "$(dirname "$0")/.."
if [[ ! -d .git ]]; then git init -b main; fi
git add .
if ! git diff --cached --quiet; then git commit -m "Initial literature tracker"; fi
if ! gh repo view "${OWNER}/${REPO}" >/dev/null 2>&1; then
  gh repo create "${OWNER}/${REPO}" --public --source=. --remote=origin --push
else
  echo "Repository exists; using it without changing visibility."
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/${OWNER}/${REPO}.git"
  git push --set-upstream origin main
fi
# The Pages REST API permits build_type=workflow. If provisioning is restricted,
# the user can still enable Source=GitHub Actions from Settings > Pages.
if gh api "repos/${OWNER}/${REPO}/pages" >/dev/null 2>&1; then
  echo "Pages already configured."
else
  if gh api --method POST "repos/${OWNER}/${REPO}/pages" -f build_type=workflow >/dev/null; then
    echo "GitHub Pages enabled (workflow source)."
  else
    echo "Pages provisioning requires repo admin: Settings > Pages > Source: GitHub Actions"
  fi
fi
printf '\nGitHub repo: https://github.com/%s/%s\n' "$OWNER" "$REPO"
printf 'Run now: https://github.com/%s/%s/actions/workflows/literature.yml\n' "$OWNER" "$REPO"
printf 'Future dashboard: https://%s.github.io/%s/\n' "$OWNER" "$REPO"
echo "Click Actions > Medical & Ophthalmic AI Literature > Run workflow."
