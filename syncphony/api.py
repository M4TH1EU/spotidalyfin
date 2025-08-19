from fastapi import FastAPI

from syncphony.db.db import init_db
from syncphony.routers import accounts, sync
from syncphony.tasks.runner import start_task_runner

app = FastAPI(title="Syncphony API")


@app.on_event("startup")
def on_startup():
    init_db()
    start_task_runner()  # start background daemon


app.include_router(accounts.router, prefix="/accounts", tags=["Accounts"])
app.include_router(sync.router, prefix="/sync", tags=["Sync"])


@app.get("/")
def read_root():
    return {"message": "Welcome to Syncphony App"}
