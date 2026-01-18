@echo off
REM Wrapper for standard snmpwalk tool
REM Usage: snmpwalk.bat [OID] [host[:port]] [community]
REM Example: snmpwalk.bat
REM Example: snmpwalk.bat .1.3.6.1.2.1.1
REM Example: snmpwalk.bat .1.3.6.1.4.1.99999
REM Example: snmpwalk.bat system 192.168.1.100:161 private

setlocal

set OID=%1
set HOST=%2
set COMMUNITY=%3

if "%OID%"=="" set OID=.1
if "%HOST%"=="" set HOST=127.0.0.1
if "%COMMUNITY%"=="" set COMMUNITY=public

snmpwalk -v 2c -c %COMMUNITY% %HOST% %OID%

