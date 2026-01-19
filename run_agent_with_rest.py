
import threading
from app.agent import SNMPAgent
from app import api
import uvicorn

if __name__ == "__main__":
    agent = SNMPAgent(port=10161)  # Use non-privileged port
    api.snmp_agent = agent
    # Start SNMP agent in a background thread
    t = threading.Thread(target=agent.run, daemon=True)
    t.start()
    # Start REST API (FastAPI/Uvicorn)
    uvicorn.run("app.api:app", host="127.0.0.1", port=6060, reload=False)
