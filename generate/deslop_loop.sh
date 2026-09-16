#!/bin/bash
export PATH="/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin:/c/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:$PATH"
cd /c/Users/Administrator/WorkBuddy/2026-08-30-22-49-28/821224.com
export AGNES_API_KEY=sk-Gk3y1g10J6LNbFOOsZNReWSFERZwugKSkiqmXZddA6cha8T5
TOTAL=225
for n in $(seq 1 30); do
  python -u generate/deslop_rewrite_html.py >> /tmp/deslop821.log 2>&1
  done=$(wc -l < .deslop_done.txt 2>/dev/null || echo 0)
  echo "[loop $n] deslop exited rc=$? done=$done" >> /tmp/deslop821.log
  if [ "$done" -ge "$TOTAL" ]; then
    echo "[loop $n] ALL DONE ($done/$TOTAL)" >> /tmp/deslop821.log
    break
  fi
  # small gap before respawn (script is checkpoint-based, resumes automatically)
  sleep 3
done
echo "[wrapper] finished at $(date)" >> /tmp/deslop821.log
