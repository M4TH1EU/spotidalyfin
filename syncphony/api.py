from fastapi import FastAPI

from syncphony.db.db import init_db
from syncphony.routers import accounts

app = FastAPI(title="Syncphony API")


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(accounts.router, prefix="/accounts", tags=["Accounts"])


@app.get("/")
def read_root():
    return {"message": "Welcome to Syncphony App"}
