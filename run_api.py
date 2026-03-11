import uvicorn

if __name__ == "__main__":
    print("Starting HR Hiring Bot FastAPI Server...")
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)
