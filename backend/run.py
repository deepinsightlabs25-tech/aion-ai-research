import os
import uvicorn

if __name__ == "__main__":
    reload = os.getenv("ENV", "production").lower() != "production"
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=reload)
