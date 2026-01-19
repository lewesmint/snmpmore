import threading
import sys
from app.agent import SNMPAgent
from app import api
from app.compiler import MibCompilationError
import uvicorn

if __name__ == "__main__":
    try:
        # Listen on all interfaces (0.0.0.0) so it's accessible from network
        agent = SNMPAgent(host='0.0.0.0', port=11161)
        api.snmp_agent = agent
        # Start SNMP agent in a background thread
        t = threading.Thread(target=agent.run, daemon=True)
        t.start()
        # Start REST API (FastAPI/Uvicorn) - also on all interfaces
        uvicorn.run("app.api:app", host="0.0.0.0", port=6060, reload=False)
    except MibCompilationError as e:
        # Print clean error message without traceback
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
    except Exception as e:
        # For unexpected errors, show the error but not full traceback
        print(f"\nERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
