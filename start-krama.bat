@echo off
rem Start the whole Krama stack (Docker services, API, web app) in real mode. See scripts\start.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
