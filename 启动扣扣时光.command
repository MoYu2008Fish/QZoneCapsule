#!/bin/zsh
cd -- "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  print '请先按 README 安装桌面版依赖。'
  read -k 1
  exit 1
fi
.venv/bin/python -m qzone_archiver.desktop
