@echo off
REM Wrapper for standard snmpset tool
REM Usage: snmpset.bat <OID> <type> <value> [host[:port]] [community]
REM Types: i=integer, u=unsigned, t=timeticks, a=ipaddress, o=oid, s=string, x=hex, d=decimal
REM Example: snmpset.bat .1.3.6.1.2.1.1.1.0 s "My System Description"
REM Example: snmpset.bat .1.3.6.1.4.1.99999.1.1.0 s "Hello World"
REM Example: snmpset.bat .1.3.6.1.4.1.99999.1.2.0 i 42

setlocal

set OID=%1
set TYPE=%2
set VALUE=%3
set HOST=%4
set COMMUNITY=%5

if "%OID%"=="" (
    echo Usage: snmpset.bat ^<OID^> ^<type^> ^<value^> [host[:port]] [community]
    echo Types: i=integer, u=unsigned, t=timeticks, a=ipaddress, o=oid, s=string, x=hex, d=decimal
    echo Example: snmpset.bat .1.3.6.1.2.1.1.1.0 s "My System"
    exit /b 1
)

if "%TYPE%"=="" (
    echo Error: Type is required
    exit /b 1
)

if "%VALUE%"=="" (
    echo Error: Value is required
    exit /b 1
)

if "%HOST%"=="" set HOST=127.0.0.1
if "%COMMUNITY%"=="" set COMMUNITY=public

snmpset -v 2c -c %COMMUNITY% %HOST% %OID% %TYPE% %VALUE%
    echo Error: Value is required
    exit /b 1
)

if "%HOST%"=="" set HOST=127.0.0.1:11161
if "%COMMUNITY%"=="" set COMMUNITY=public

"%~dp0SnmpSet.exe" -r:%HOST% -c:%COMMUNITY% -v:v2c -o:%OID% -tp:%TYPE% -vl:%VALUE%

