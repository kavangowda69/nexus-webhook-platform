from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/test")
async def receive_webhook(request: Request):
    payload = await request.json()

    print(
        f"Webhook received | user={payload.get('user_id')} | payload={payload.get('payload')}"
    )

    return {"status": "ok"}