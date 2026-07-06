from fastapi import FastAPI

app = FastAPI(title="DOT Interview Backend")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
