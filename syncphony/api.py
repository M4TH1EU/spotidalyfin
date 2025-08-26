import musicbrainzngs
from fastapi import FastAPI

from syncphony.db.db import init_db
from syncphony.routers import accounts, sync, tasks, download
from syncphony.tasks.runner import TaskRunner
from syncphony.utils.logger import setup_logger

app = FastAPI(title="Syncphony API")

runner = TaskRunner()


@app.on_event("startup")
def on_startup():
    setup_logger()
    musicbrainzngs.set_useragent("syncphony", "0.1")
    init_db()
    runner.start()


@app.on_event("shutdown")
def on_shutdown():
    runner.stop()


app.include_router(accounts.router, prefix="/accounts", tags=["Accounts"])
app.include_router(sync.router, prefix="/sync", tags=["Sync"])
app.include_router(download.router, prefix="/download", tags=["Download"])
app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])


@app.get("/")
def read_root():
    return {"message": "Welcome to Syncphony App"}
