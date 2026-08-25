@echo off
cd /d "%~dp0"
"C:\Program Files\Git\git-bash.exe" -c "tmux new -s opencode || true; exec opencode --continue"