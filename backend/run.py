import uvicorn

if __name__ == "__main__":
    # running the server with hot reload enabled for development
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
