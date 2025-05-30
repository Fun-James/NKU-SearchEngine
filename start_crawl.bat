@echo off
chcp 65001 >nul
echo ====================================
echo Nankai University Web Crawler Tool
echo ====================================
echo.

echo Checking Elasticsearch service...
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:9200' -TimeoutSec 5 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Elasticsearch service not running!
    echo Please start Elasticsearch service first
    echo You can download and start Elasticsearch from: https://www.elastic.co/downloads/elasticsearch
    pause
    exit /b 1
)
echo [OK] Elasticsearch service is running

echo.
echo Select crawling mode:
echo 1. Quick test (50 pages)
echo 2. Medium scale (10000 pages)
echo 3. Large scale (100000 pages)
echo 4. Batch crawling (Recommended)
echo 5. Custom parameters

set /p choice="请输入选择 (1-5): "

rem 设置Python环境变量以支持正确的编码
set PYTHONIOENCODING=utf-8
set PYTHONLEGACYWINDOWSSTDIO=utf-8

if "%choice%"=="1" (
    echo 开始快速测试爬取...
    python -X utf8 crawl_and_index.py --total-pages 30 --main-ratio 0.09 --delay 0.5 --max-depth 5 --skip-robots
) else if "%choice%"=="2" (
    echo 开始中等规模爬取...
    python -X utf8 crawl_and_index.py --total-pages 3500 --main-ratio 0.09 --delay 0.3 --max-depth 5 --skip-robots
) else if "%choice%"=="3" (
    echo 开始大规模爬取...
    echo [警告] 这将花费数小时时间，确保系统稳定运行
    pause
    python -X utf8 crawl_and_index.py --total-pages 100000 --main-ratio 0.09 --delay 0.2 --max-depth 5 --skip-robots
) else if "%choice%"=="4" (
    echo 启动分批次爬取工具...
    python -X utf8 batch_crawl.py
) else if "%choice%"=="5" (
    echo 启动自定义参数界面...
    python -X utf8 batch_crawl.py
) else (
    echo 无效选择
    pause
    exit /b 1
)

echo.
echo 爬取任务完成！
pause
