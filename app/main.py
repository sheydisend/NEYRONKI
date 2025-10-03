from fastapi import FastAPI
from app.database import get_db, engine
from app import models, schemas 

app = FastAPI(title="Video Preferences API", version="1.0.0")

models.Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return "Video Preferences API"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)