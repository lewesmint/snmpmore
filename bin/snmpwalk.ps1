
<#
.SYNOPSIS
    Wrapper for standard snmpwalk tool
.DESCRIPTION
    Simplified SNMP WALK command with defaults:
    - Host: 127.0.0.1
    - Community: public
    - Version: v2c
.PARAMETER OID
    The OID to walk (optional, defaults to .1 for entire tree)
.PARAMETER Host
    Target host (default: 127.0.0.1)
.PARAMETER Community
    SNMP community string (default: public)
.EXAMPLE
    .\snmpwalk.ps1
    .\snmpwalk.ps1 .1.3.6.1.2.1.1
    .\snmpwalk.ps1 .1.3.6.1.4.1.99999
    .\snmpwalk.ps1 system -Host 192.168.1.100
#>

param(
    [Parameter(Mandatory=$false, Position=0)]
    [string]$OID = ".1",
    [Parameter(Mandatory=$false)]
    [string]$Host = "127.0.0.1",
    [Parameter(Mandatory=$false)]
    [string]$Community = "public",
    [Parameter(Mandatory=$false)]
    [ValidateSet("v1", "v2c", "v3")]
    [string]$Version = "v2c"
)

snmpwalk -v $Version -c $Community $Host $OID

