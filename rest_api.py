from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Reference to the SNMPAgent instance will be set by main app
snmp_agent = None

app = FastAPI()

class SysDescrUpdate(BaseModel):
    value: str

@app.get("/sysdescr")
def get_sysdescr():
    if snmp_agent is None:
        raise HTTPException(status_code=500, detail="SNMP agent not initialized")
    # sysDescr OID: (1,3,6,1,2,1,1,1,0)
    oid = (1, 3, 6, 1, 2, 1, 1, 1, 0)
    try:
        value = snmp_agent.get_scalar_value(oid)
        return {"oid": oid, "value": value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting sysDescr: {str(e)}")

@app.post("/sysdescr")
def set_sysdescr(update: SysDescrUpdate):
    if snmp_agent is None:
        raise HTTPException(status_code=500, detail="SNMP agent not initialized")
    oid = (1, 3, 6, 1, 2, 1, 1, 1, 0)
    try:
        snmp_agent.set_scalar_value(oid, update.value)
        return {"status": "ok", "oid": oid, "new_value": update.value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting sysDescr: {str(e)}")
