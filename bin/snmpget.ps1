
<#
.SYNOPSIS
    Wrapper for standard snmpget tool
.DESCRIPTION
    Simplified SNMP GET command with defaults:
    - Host: 127.0.0.1
    - Community: public
    - Version: v2c
.PARAMETER OID
    The OID to query (required)
.PARAMETER Host
    Target host (default: 127.0.0.1)
.PARAMETER Community
    SNMP community string (default: public)
.EXAMPLE
    .\snmpget.ps1 .1.3.6.1.2.1.1.1.0
    .\snmpget.ps1 sysDescr.0
    .\snmpget.ps1 .1.3.6.1.4.1.99999.1.1.0 -Host 192.168.1.100
#>

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$OID,
    [Parameter(Mandatory=$false)]
    [string]$Host = "127.0.0.1",
    [Parameter(Mandatory=$false)]
    [string]$Community = "public",
    [Parameter(Mandatory=$false)]
    [ValidateSet("v1", "v2c", "v3")]
    [string]$Version = "v2c"
)

snmpget -v $Version -c $Community $Host $OID

