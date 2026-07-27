#!/bin/sh
# Set this repo's git identity from the currently active GitHub account.
#
# Both authors share a machine. Run this at the start of your session,
# after `gh auth switch --user <you>`. The pre-commit hook checks the two
# agree, so forgetting is caught rather than silently misattributed.
#
#   gh auth switch --user Borno0007
#   sh scripts/set-identity.sh
#
# Sets --local only: your global git config is left alone.

set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
AUTHORS="$REPO_ROOT/.githooks/authors.txt"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install it, or set the identity by hand:"
  echo "  git config --local user.name  \"Your Name\""
  echo "  git config --local user.email \"you@example.com\""
  exit 1
fi

active=$(gh api user --jq .login 2>/dev/null || true)
if [ -z "$active" ]; then
  echo "Not authenticated to GitHub. Run:  gh auth login"
  exit 1
fi

row=$(grep -v '^#' "$AUTHORS" | grep -i "^$active|" || true)
if [ -z "$row" ]; then
  echo "GitHub account '$active' is not in .githooks/authors.txt."
  echo "Add a line there in the form:  login|Full Name|email"
  exit 1
fi

name=$(echo "$row" | cut -d'|' -f2)
email=$(echo "$row" | cut -d'|' -f3)

git config --local user.name "$name"
git config --local user.email "$email"

echo "Active GitHub account : $active"
echo "Commits now authored as: $name <$email>"
