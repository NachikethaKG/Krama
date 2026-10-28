@echo off
rem Stop the Krama API, web app and Docker services. See scripts\stop.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1" %*
