from fastapi import FastAPI

app = FastAPI(
    title="Engineer Department Platform API",
    version="5.0.0"
)

@app.get("/")
def root():
    return {
        "status":"ok",
        "service":"Engineer Department Platform API",
        "version":"V5.0 Enterprise"
    }

@app.get("/health")
def health():
    return {"status":"healthy"}
