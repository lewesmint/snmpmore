@echo off
REM Quick script to walk the system group (SNMPv2-MIB)
echo Walking system group (.1.3.6.1.2.1.1) from 127.0.0.1...
snmpwalk -v 2c -c public 127.0.0.1 .1.3.6.1.2.1.1

