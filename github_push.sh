#!/bin/bash
git add .
git commit -m "Auto update: $(date +'%Y-%m-%d %H:%M:%S')"
git push -u origin main
echo "✅ GitHubへのプッシュが完了しました！"
