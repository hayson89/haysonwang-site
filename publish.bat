@echo off
chcp 65001 >nul

cd /d E:\Website\quartz

echo ============================
echo 添加所有网站修改
echo ============================

git add .

echo ============================
echo 提交更新
echo ============================

git commit -m "update website"

echo ============================
echo 推送 GitHub
echo ============================

git push

echo ============================
echo 发布完成
echo ============================

pause