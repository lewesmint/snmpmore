@echo off
REM Wrapper for standard snmpget tool
REM Usage: snmpget.bat <OID> [host[:port]] [community]
REM Example: snmpget.bat .1.3.6.1.2.1.1.1.0
REM Example: snmpget.bat sysDescr.0
REM Example: snmpget.bat .1.3.6.1.4.1.99999.1.1.0 192.168.1.100:161 private

setlocal

set OID=%1
set HOST=%2
set COMMUNITY=%3

if "%OID%"=="" (
    echo Usage: snmpget.bat ^<OID^> [host[:port]] [community]
    echo Example: snmpget.bat .1.3.6.1.2.1.1.1.0
    exit /b 1
)

if "%HOST%"=="" set HOST=127.0.0.1
if "%COMMUNITY%"=="" set COMMUNITY=public

snmpget -v 2c -c %COMMUNITY% %HOST% %OID%

