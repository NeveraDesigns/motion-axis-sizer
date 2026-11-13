#!/bin/bash
# Double-click to publish this folder's latest version to GitHub.
# The online app (Streamlit) picks up the new version a minute or two later.
#
# First run only: connects this folder to GitHub and signs you in through
# your browser (GitHub's official command-line tool, "gh", is downloaded into
# ~/.motion-sizer-tools). After that, publishing takes a few seconds.

REPO_URL="${MS_REPO_URL:-https://github.com/NeveraDesigns/motion-axis-sizer.git}"
REPO_PAGE="https://github.com/NeveraDesigns/motion-axis-sizer"
AUTHOR_NAME="Daniel Zubovic"
AUTHOR_EMAIL="NeveraDesigns@users.noreply.github.com"
TOOLS="$HOME/.motion-sizer-tools"

cd "$(dirname "$0")" || exit 1
echo "=== Publish Motion Axis Sizer to GitHub ==="
echo ""

pause_exit() { echo ""; read -r -p "Press Enter to close..."; exit "$1"; }

# 1. git (comes with Apple's command line developer tools)
if ! git --version >/dev/null 2>&1; then
  echo "Git isn't installed yet. If a pop-up asks to install 'command line developer"
  echo "tools', click Install, wait for it to finish, then double-click this file again."
  xcode-select --install >/dev/null 2>&1
  pause_exit 1
fi

# 2. GitHub sign-in tool (gh), downloaded once from GitHub's official releases
GH="$(command -v gh || true)"
if [ -z "$GH" ] && [ -x "$TOOLS/bin/gh" ]; then GH="$TOOLS/bin/gh"; fi
if [ -z "$GH" ]; then
  echo "One-time setup: downloading GitHub's sign-in tool..."
  ARCH="$(uname -m)"; [ "$ARCH" = "x86_64" ] && ARCH="amd64"
  ZIP_URL="$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest | python3 -c "
import json, sys
assets = json.load(sys.stdin)['assets']
print(next(a['browser_download_url'] for a in assets if a['name'].endswith('_macOS_$ARCH.zip')))")"
  if [ -z "$ZIP_URL" ]; then echo "Couldn't find the download. Check your internet and try again."; pause_exit 1; fi
  mkdir -p "$TOOLS/dl" "$TOOLS/bin"
  curl -fsSL "$ZIP_URL" -o "$TOOLS/dl/gh.zip" && unzip -oq "$TOOLS/dl/gh.zip" -d "$TOOLS/dl" \
    && cp "$TOOLS"/dl/gh_*/bin/gh "$TOOLS/bin/gh" && chmod +x "$TOOLS/bin/gh" \
    || { echo "Download failed. Check your internet and try again."; pause_exit 1; }
  GH="$TOOLS/bin/gh"
  echo "Done."
  echo ""
fi

# 3. Sign in to GitHub (first time only)
if ! "$GH" auth status -h github.com >/dev/null 2>&1; then
  echo "One-time sign-in to GitHub."
  echo "  1. Copy the code shown below."
  echo "  2. Press Enter. Your browser opens GitHub; paste the code and click Authorize."
  echo "  3. If asked 'Authenticate Git with your GitHub credentials?', press Enter (Yes)."
  echo ""
  "$GH" auth login -h github.com -p https -w || { echo "Sign-in didn't finish. Try again."; pause_exit 1; }
fi
"$GH" auth setup-git -h github.com >/dev/null 2>&1

# 4. Connect this folder to the GitHub repository (first time only)
if [ ! -d .git ]; then
  echo "Connecting this folder to $REPO_PAGE ..."
  git init -q -b main
  git remote add origin "$REPO_URL"
  git fetch -q origin main || { echo "Couldn't reach GitHub."; rm -rf .git; pause_exit 1; }
  git reset -q origin/main      # keep your files exactly as they are
  echo "Connected."
  echo ""
fi
git config user.name "$AUTHOR_NAME"
git config user.email "$AUTHOR_EMAIL"

# 5. Anything new?
git add -A
if git diff --cached --quiet; then
  echo "Nothing new to publish. GitHub already has your latest version."
  pause_exit 0
fi
echo "Changes to publish:"
git diff --cached --stat | sed 's/^/  /'
echo ""
read -r -t 60 -p "Short note about what changed (or just press Enter): " NOTE
echo ""
[ -z "$NOTE" ] && NOTE="Update from Mac ($(date '+%Y-%m-%d %H:%M'))"
git commit -q -m "$NOTE"

# 6. Bring in anything published from elsewhere, then upload
git fetch -q origin main
if ! git rebase -q origin/main; then
  git rebase --abort
  echo "GitHub has changes that clash with yours, so nothing was uploaded."
  echo "Your files are untouched. Ask Claude to help merge them."
  pause_exit 1
fi
if git push -q origin main; then
  echo "Published. $REPO_PAGE"
  echo "The online app updates in a minute or two."
  pause_exit 0
else
  echo "Upload failed. Check your internet, then double-click this file again."
  pause_exit 1
fi
