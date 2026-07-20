#!/bin/sh
# 공고 수집 후 GitHub Pages로 자동 배포 (launchd가 매일 실행)
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "$HOME/un-job-monitor" || exit 1

/usr/bin/python3 check.py
git pull --rebase --autostash -q
git add data.js seen.json
git diff --cached --quiet || git commit -q -m "data: $(date '+%Y-%m-%d %H:%M')"
git push -q
