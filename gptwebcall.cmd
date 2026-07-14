@echo off
setlocal
pushd "%~dp0"
python -m companion.cli --root "%~dp0." %*
set "exit_code=%ERRORLEVEL%"
popd
exit /b %exit_code%
