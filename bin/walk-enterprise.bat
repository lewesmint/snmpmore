@echo off
REM Quick script to walk the enterprise MIB (.1.3.6.1.4.1.99999)
echo Walking enterprise MIB (.1.3.6.1.4.1.99999) from 127.0.0.1...
snmpwalk -v 2c -c public 127.0.0.1 .1.3.6.1.4.1.99999

