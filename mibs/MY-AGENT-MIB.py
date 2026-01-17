# SNMP MIB module (MY-AGENT-MIB) expressed in pysnmp data model.
#
# This Python module is designed to be imported and executed by the
# pysnmp library.
#
# See https://www.pysnmp.com/pysnmp for further information.
#
# Notes
# -----
# ASN.1 source file://./MY-AGENT-MIB.txt
# Produced by pysmi-1.6.2 at Fri Jan 16 14:36:32 2026
# On host parrot platform Linux version 6.8.0-90-generic by user mintz
# Using Python version 3.10.16 (main, Dec 29 2025, 01:44:12) [GCC 13.3.0]

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
 enterprises,
 iso) = mibBuilder.importSymbols(
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
    "enterprises",
    "iso")

(DisplayString,
 PhysAddress,
 TextualConvention) = mibBuilder.importSymbols(
    "SNMPv2-TC",
    "DisplayString",
    "PhysAddress",
    "TextualConvention")


# MODULE-IDENTITY

myAgent = ModuleIdentity(
    (1, 3, 6, 1, 4, 1, 99999)
)


# Types definitions


# TEXTUAL-CONVENTIONS



# MIB Managed Objects in the order of their OIDs

_MyString_Type = DisplayString
_MyString_Object = MibScalar
myString = _MyString_Object(
    (1, 3, 6, 1, 4, 1, 99999, 1),
    _MyString_Type()
)
myString.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    myString.setStatus("current")
_MyCounter_Type = Integer32
_MyCounter_Object = MibScalar
myCounter = _MyCounter_Object(
    (1, 3, 6, 1, 4, 1, 99999, 2),
    _MyCounter_Type()
)
myCounter.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    myCounter.setStatus("current")
_MyGauge_Type = Integer32
_MyGauge_Object = MibScalar
myGauge = _MyGauge_Object(
    (1, 3, 6, 1, 4, 1, 99999, 3),
    _MyGauge_Type()
)
myGauge.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    myGauge.setStatus("current")
_MyTable_Object = MibTable
myTable = _MyTable_Object(
    (1, 3, 6, 1, 4, 1, 99999, 4)
)
if mibBuilder.loadTexts:
    myTable.setStatus("current")
_MyTableEntry_Object = MibTableRow
myTableEntry = _MyTableEntry_Object(
    (1, 3, 6, 1, 4, 1, 99999, 4, 1)
)
myTableEntry.setIndexNames(
    (0, "MY-AGENT-MIB", "myTableIndex"),
)
if mibBuilder.loadTexts:
    myTableEntry.setStatus("current")
_MyTableIndex_Type = Integer32
_MyTableIndex_Object = MibTableColumn
myTableIndex = _MyTableIndex_Object(
    (1, 3, 6, 1, 4, 1, 99999, 4, 1, 1),
    _MyTableIndex_Type()
)
myTableIndex.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    myTableIndex.setStatus("current")
_MyTableName_Type = DisplayString
_MyTableName_Object = MibTableColumn
myTableName = _MyTableName_Object(
    (1, 3, 6, 1, 4, 1, 99999, 4, 1, 2),
    _MyTableName_Type()
)
myTableName.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    myTableName.setStatus("current")
_MyTableValue_Type = Integer32
_MyTableValue_Object = MibTableColumn
myTableValue = _MyTableValue_Object(
    (1, 3, 6, 1, 4, 1, 99999, 4, 1, 3),
    _MyTableValue_Type()
)
myTableValue.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    myTableValue.setStatus("current")
_MyTableStatus_Type = DisplayString
_MyTableStatus_Object = MibTableColumn
myTableStatus = _MyTableStatus_Object(
    (1, 3, 6, 1, 4, 1, 99999, 4, 1, 4),
    _MyTableStatus_Type()
)
myTableStatus.setMaxAccess("read-only")
if mibBuilder.loadTexts:
    myTableStatus.setStatus("current")

# Managed Objects groups


# Notification objects


# Notifications groups


# Agent capabilities


# Module compliance


# Export all MIB objects to the MIB builder

mibBuilder.exportSymbols(
    "MY-AGENT-MIB",
    **{"myAgent": myAgent,
       "myString": myString,
       "myCounter": myCounter,
       "myGauge": myGauge,
       "myTable": myTable,
       "myTableEntry": myTableEntry,
       "myTableIndex": myTableIndex,
       "myTableName": myTableName,
       "myTableValue": myTableValue,
       "myTableStatus": myTableStatus}
)
