# 一键启动前后端（需两个终端窗口）
# 终端 1：后端 API
# 终端 2：前端 Streamlit

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  ThinkRAG 本地启动脚本" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "请在两个终端分别执行：" -ForegroundColor Yellow
Write-Host ""
Write-Host "[终端 1] 启动 API 后端:" -ForegroundColor Green
Write-Host '  $env:PYTHONPATH = "C:\Users\ethan1.zhao\Downloads\agent-kb-main\github-agent-kb"' -ForegroundColor White
Write-Host '  python run_api.py' -ForegroundColor White
Write-Host ""
Write-Host "[终端 2] 启动前端 (Streamlit):" -ForegroundColor Green
Write-Host '  $env:PYTHONPATH = "C:\Users\ethan1.zhao\Downloads\agent-kb-main\github-agent-kb"' -ForegroundColor White
Write-Host '  streamlit run frontend/Document_QA.py' -ForegroundColor White
Write-Host ""
Write-Host "后端地址: http://127.0.0.1:18080" -ForegroundColor Cyan
Write-Host "前端地址: http://192.168.1.24:8501 (Streamlit 启动后显示)" -ForegroundColor Cyan
Write-Host "API 文档: http://127.0.0.1:18080/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
