# SNMP MIB module (INET-ADDRESS-MIB) expressed in pysnmp data model.
#
# This Python module is designed to be imported and executed by the
# pysnmp library.
#
# See https://www.pysnmp.com/pysnmp for further information.
#
# Notes
# -----
# ASN.1 source file://c:\net-snmp\share\snmp\mibs\INET-ADDRESS-MIB.txt
# Produced by pysmi-1.6.2 at Mon Jan 19 13:11:57 2026
# On host Tungsten platform Windows version 11 by user mintz
# Using Python version 3.13.2 (tags/v3.13.2:4f8bb39, Feb  4 2025, 16:24:41) [MSC v.1942 64 bit (ARM64)]

if 'mibBuilder' not in globals():
    import sys

    sys.stderr.write(__doc__)
    sys.exit(1)

# Import base ASN.1 objects even if this MIB does not use it

(Integer,
 OctetString,
 ObjectIdentifier) = mibBuilder.importSymbols(
    "ASN1",
    "Integer",
    "OctetString",
    "ObjectIdentifier")

(NamedValues,) = mibBuilder.importSymbols(
    "ASN1-ENUMERATION",
    "NamedValues")
(ConstraintsIntersection,
 ConstraintsUnion,
 SingleValueConstraint,
 ValueRangeConstraint,
 ValueSizeConstraint) = mibBuilder.importSymbols(
    "ASN1-REFINEMENT",
    "ConstraintsIntersection",
    "ConstraintsUnion",
    "SingleValueConstraint",
    "ValueRangeConstraint",
    "ValueSizeConstraint")

# Import SMI symbols from the MIBs this MIB depends on

(ModuleCompliance,
 NotificationGroup) = mibBuilder.importSymbols(
    "SNMPv2-CONF",
    "ModuleCompliance",
    "NotificationGroup")

(Bits,
 Counter32,
 Counter64,
 Gauge32,
 Integer32,
 IpAddress,
 ModuleIdentity,
 MibIdentifier,
 NotificationType,
 ObjectIdentity,
 MibScalar,
 MibTable,
 MibTableRow,
 MibTableColumn,
 TimeTicks,
 Unsigned32,
 iso,
 mib_2) = mibBuilder.importSymbols(
    "SNMPv2-SMI",
    "Bits",
    "Counter32",
    "Counter64",
    "Gauge32",
    "Integer32",
    "IpAddress",
    "ModuleIdentity",
    "MibIdentifier",
    "NotificationType",
    "ObjectIdentity",
    "MibScalar",
    "MibTable",
    "MibTableRow",
    "MibTableColumn",
    "TimeTicks",
    "Unsigned32",
    "iso",
    "mib-2")

(DisplayString,
 PhysAddress,
 TextualConvention) = mibBuilder.importSymbols(
    "SNMPv2-TC",
    "DisplayString",
    "PhysAddress",
    "TextualConvention")


# MODULE-IDENTITY

inetAddressMIB = ModuleIdentity(
    (1, 3, 6, 1, 2, 1, 76)
)
if mibBuilder.loadTexts:
    inetAddressMIB.setRevisions(
        ("2005-02-04 00:00",
         "2002-05-09 00:00",
         "2000-06-08 00:00")
    )


# Types definitions


# TEXTUAL-CONVENTIONS



class InetAddressType(TextualConvention, Integer32):
    status = "current"
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        SingleValueConstraint(
            *(0,
              1,
              2,
              3,
              4,
              16)
        )
    )
    namedValues = NamedValues(
        *(("unknown", 0),
          ("ipv4", 1),
          ("ipv6", 2),
          ("ipv4z", 3),
          ("ipv6z", 4),
          ("dns", 16))
    )



class InetAddress(TextualConvention, OctetString):
    status = "current"
    subtypeSpec = OctetString.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueSizeConstraint(0, 255),
    )



class InetAddressIPv4(TextualConvention, OctetString):
    status = "current"
    displayHint = "1d.1d.1d.1d"
    subtypeSpec = OctetString.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueSizeConstraint(4, 4),
    )
    fixed_length = 4



class InetAddressIPv6(TextualConvention, OctetString):
    status = "current"
    displayHint = "2x:2x:2x:2x:2x:2x:2x:2x"
    subtypeSpec = OctetString.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueSizeConstraint(16, 16),
    )
    fixed_length = 16



class InetAddressIPv4z(TextualConvention, OctetString):
    status = "current"
    displayHint = "1d.1d.1d.1d%4d"
    subtypeSpec = OctetString.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueSizeConstraint(8, 8),
    )
    fixed_length = 8



class InetAddressIPv6z(TextualConvention, OctetString):
    status = "current"
    displayHint = "2x:2x:2x:2x:2x:2x:2x:2x%4d"
    subtypeSpec = OctetString.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueSizeConstraint(20, 20),
    )
    fixed_length = 20



class InetAddressDNS(TextualConvention, OctetString):
    status = "current"
    displayHint = "255a"
    subtypeSpec = OctetString.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueSizeConstraint(1, 255),
    )



class InetAddressPrefixLength(TextualConvention, Unsigned32):
    status = "current"
    displayHint = "d"
    subtypeSpec = Unsigned32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(0, 2040),
    )



class InetPortNumber(TextualConvention, Unsigned32):
    status = "current"
    displayHint = "d"
    subtypeSpec = Unsigned32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        ValueRangeConstraint(0, 65535),
    )



class InetAutonomousSystemNumber(TextualConvention, Unsigned32):
    status = "current"
    displayHint = "d"


class InetScopeType(TextualConvention, Integer32):
    status = "current"
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        SingleValueConstraint(
            *(1,
              2,
              3,
              4,
              5,
              8,
              14)
        )
    )
    namedValues = NamedValues(
        *(("interfaceLocal", 1),
          ("linkLocal", 2),
          ("subnetLocal", 3),
          ("adminLocal", 4),
          ("siteLocal", 5),
          ("organizationLocal", 8),
          ("global", 14))
    )



class InetZoneIndex(TextualConvention, Unsigned32):
    status = "current"
    displayHint = "d"


class InetVersion(TextualConvention, Integer32):
    status = "current"
    subtypeSpec = Integer32.subtypeSpec
    subtypeSpec += ConstraintsUnion(
        SingleValueConstraint(
            *(0,
              1,
              2)
        )
    )
    namedValues = NamedValues(
        *(("unknown", 0),
          ("ipv4", 1),
          ("ipv6", 2))
    )



# MIB Managed Objects in the order of their OIDs


# Managed Objects groups


# Notification objects


# Notifications groups


# Agent capabilities


# Module compliance


# Export all MIB objects to the MIB builder

mibBuilder.exportSymbols(
    "INET-ADDRESS-MIB",
    **{"InetAddressType": InetAddressType,
       "InetAddress": InetAddress,
       "InetAddressIPv4": InetAddressIPv4,
       "InetAddressIPv6": InetAddressIPv6,
       "InetAddressIPv4z": InetAddressIPv4z,
       "InetAddressIPv6z": InetAddressIPv6z,
       "InetAddressDNS": InetAddressDNS,
       "InetAddressPrefixLength": InetAddressPrefixLength,
       "InetPortNumber": InetPortNumber,
       "InetAutonomousSystemNumber": InetAutonomousSystemNumber,
       "InetScopeType": InetScopeType,
       "InetZoneIndex": InetZoneIndex,
       "InetVersion": InetVersion,
       "inetAddressMIB": inetAddressMIB}
)
