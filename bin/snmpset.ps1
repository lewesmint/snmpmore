
<#
.SYNOPSIS
    Wrapper for standard snmpset tool
.DESCRIPTION
    Simplified SNMP SET command with defaults:
    - Host: 127.0.0.1
    - Community: public
    - Version: v2c
.PARAMETER OID
    The OID to set (required)
.PARAMETER Type
    Data type: i (integer), u (unsigned), t (timeticks), a (ipaddress), o (oid), s (string), x (hex), d (decimal)
.PARAMETER Value
    The value to set (required)
.PARAMETER Host
    Target host (default: 127.0.0.1)
.PARAMETER Community
    SNMP community string (default: public)
.EXAMPLE
    .\snmpset.ps1 .1.3.6.1.2.1.1.1.0 s "My System Description"
    .\snmpset.ps1 .1.3.6.1.4.1.99999.1.1.0 s "Hello World"
    .\snmpset.ps1 .1.3.6.1.4.1.99999.1.2.0 i 42
#>

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$OID,
    [Parameter(Mandatory=$true, Position=1)]
    [ValidateSet("i", "u", "t", "a", "o", "s", "x", "d")]
    [string]$Type,
    [Parameter(Mandatory=$true, Position=2)]
    [string]$Value,
    [Parameter(Mandatory=$false)]
    [string]$Host = "127.0.0.1",
    [Parameter(Mandatory=$false)]
    [string]$Community = "public",
    [Parameter(Mandatory=$false)]
    [ValidateSet("v1", "v2c", "v3")]
    [string]$Version = "v2c"
)

snmpset -v $Version -c $Community $Host $OID $Type $Value

