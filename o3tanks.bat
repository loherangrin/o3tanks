@echo off

:main
if not "%O3TANKS_NO_CONTAINERS%" == "" goto throw_error_UNSUPPORTED_CONTAINTERS_MODE

call :check_python
if %ERRORLEVEL% neq 0 goto throw_error_MISSING_PYTHON

call :run_cli %*

exit /b %ERRORLEVEL%
goto :eof


:: --- INTERNAL FUNCTIONS ---

:check_python
setlocal

python --version > NUL 2>&1

if %ERRORLEVEL% equ 0 (
	set "NOT_FOUND=0"
) else (
	set "NOT_FOUND=1"
)

endlocal && exit /b %NOT_FOUND%
goto :eof


:run_cli
setlocal

set "PYTHONPATH=%PYTHONPATH%;%1"
set "O3TANKS_NO_CONTAINERS=1"

call python -m o3tanks.cli "%~n0" "%~f0" "-" %*

if %ERRORLEVEL% equ 0 (
	set "FAILED=0"
) else (
	set "FAILED=1"
)

endlocal && exit /b %FAILED%
goto :eof


:: --- I/O FUNCTIONS ---

:throw_error_MISSING_PYTHON
echo Unable to find 'python' on your system.
echo Please refer to Python official documentation for installation instructions:
echo https://docs.python.org/3/using/windows.html
exit /b 1


:throw_error_UNSUPPORTED_CONTAINTERS_MODE
echo Containers are not supported on Windows. Please unset any value for 'O3TANKS_NO_CONTAINERS' in your system variables
exit /b 1
