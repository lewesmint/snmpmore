@echo off
REM Quick script to get sysDescr from local agent
echo Getting sysDescr from 127.0.0.1...
snmpget -v 2c -c public 127.0.0.1 .1.3.6.1.2.1.1.1.0

