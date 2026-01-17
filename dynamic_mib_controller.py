from pysnmp.smi import builder
from pyasn1.type.univ import OctetString, Integer
from typing import List, Any
import threading

class DynamicMibController:
    def __init__(self, mibBuilder: 'builder.MibBuilder') -> None:
        # Import MibScalarInstance the pysnmp v7+ way
        (MibScalarInstance,) = mibBuilder.importSymbols('SNMPv2-SMI', 'MibScalarInstance')
        self.MibScalarInstance = MibScalarInstance
        self.counter = 0
        self.counter_lock = threading.Lock()
        self.table_rows: List[List[Any]] = [
            [1, 'sensor_a', 25, 'ok'],
            [2, 'sensor_b', 30, 'ok'],
            [3, 'sensor_c', 45, 'warning'],
        ]

    def register_scalars(self, mibBuilder: 'builder.MibBuilder') -> None:
        # Dynamic counter: increments on each SNMP GET
        def get_counter(*args: Any) -> Integer:
            with self.counter_lock:
                self.counter += 1
                return Integer(self.counter)
        mibBuilder.exportSymbols(
            '__MY_MIB',
            self.MibScalarInstance((1,3,6,1,4,1,99999,1,1), (0,), OctetString('Hello from pysnmp')),
            self.MibScalarInstance((1,3,6,1,4,1,99999,1,2), (0,), get_counter()),
            self.MibScalarInstance((1,3,6,1,4,1,99999,1,3), (0,), Integer(42)),
        )

    def register_table(self, mibBuilder: 'builder.MibBuilder') -> None:
        # Dynamic table: can be updated via update_table()
        for row in self.table_rows:
            idx, name, value, status = row
            mibBuilder.exportSymbols(
                '__MY_MIB',
                self.MibScalarInstance((1,3,6,1,4,1,99999,4,1,1,idx), (), Integer(idx)),
                self.MibScalarInstance((1,3,6,1,4,1,99999,4,1,2,idx), (), OctetString(name)),
                self.MibScalarInstance((1,3,6,1,4,1,99999,4,1,3,idx), (), Integer(value)),
                self.MibScalarInstance((1,3,6,1,4,1,99999,4,1,4,idx), (), OctetString(status)),
            )

    def update_table(self, new_rows: List[List[Any]]) -> None:
        self.table_rows = new_rows
