from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Dict, Any
import uuid

from app.database import get_db, engine
from app import models, schemas, crud
from app.services.video_analyzer import VideoAnalyzer

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Video Preferences API", version="1.0.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

video_analyzer = VideoAnalyzer()

# Хранилище сессий (в продакшене используйте Redis или базу данных)
user_sessions = {}

def get_current_user(request: Request, db: Session = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in user_sessions:
        user_id = user_sessions[session_id]
        user = crud.get_user_by_id(db, user_id)
        if user:
            return user
    return None

@app.post("/register")
def register(user: schemas.UserCreate, response: Response, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    new_user = crud.create_user(db=db, user=user)
    
    # Создаем сессию
    session_id = str(uuid.uuid4())
    user_sessions[session_id] = new_user.id
    
    # Устанавливаем cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=3600  # 1 час
    )
    
    return {"message": "Registration successful", "user_id": new_user.id}

@app.post("/login")
def login(user: schemas.UserLogin, response: Response, db: Session = Depends(get_db)):
    authenticated_user = crud.authenticate_user(db, user.email, user.password)
    if not authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Создаем сессию
    session_id = str(uuid.uuid4())
    user_sessions[session_id] = authenticated_user.id
    
    # Устанавливаем cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=3600  # 1 час
    )
    
    return {"message": "Login successful", "user_id": authenticated_user.id}

@app.post("/logout")
def logout(response: Response, request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in user_sessions:
        del user_sessions[session_id]
    
    # Удаляем cookie
    response.delete_cookie("session_id")
    return {"message": "Logout successful"}

@app.get("/users/{user_id}/preferences", response_model=schemas.PreferencesResponse)
def get_user_preferences(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user or current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    preferences = crud.get_preferences_by_user_id(db, user_id)
    if not preferences:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preferences not found for this user"
        )
    
    # Используем функцию преобразования
    return crud.preferences_to_schema(preferences)

@app.post("/users/{user_id}/preferences", response_model=schemas.PreferencesResponse)
def create_or_update_preferences(
    user_id: int,
    preferences: schemas.PreferencesCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user or current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    existing_preferences = crud.get_preferences_by_user_id(db, user_id)
    
    if existing_preferences:
        result = crud.update_user_preferences(db, preferences, user_id)
    else:
        result = crud.create_user_preferences(db, preferences, user_id)
    
    # Используем функцию преобразования для ответа
    return crud.preferences_to_schema(result)

@app.post("/analyze-video")
async def analyze_video(
    request: Dict[str, Any], 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    video_url = request.get("video_url")
    user_preferences = request.get("user_preferences", {})
    
    if not video_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video URL is required"
        )
    
    try:
        analysis_result = video_analyzer.analyze_video_suitability(video_url, user_preferences)
        return analysis_result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing video: {str(e)}"
        )

# Template Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "current_user": current_user
    })

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    if current_user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("register.html", {
        "request": request,
        "current_user": current_user
    })

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    if current_user:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "current_user": current_user
    })

@app.get("/users/{user_id}/preferences-page", response_class=HTMLResponse)
async def get_preferences_page(request: Request, user_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    if not current_user or current_user.id != user_id:
        return RedirectResponse(url="/login", status_code=303)
    
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return templates.TemplateResponse("preferences.html", {
        "request": request,
        "current_user": current_user,
        "user_id": user_id
    })

@app.get("/analyze", response_class=HTMLResponse)
async def analyze_video_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    
    return templates.TemplateResponse("analyze.html", {
        "request": request,
        "current_user": current_user
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)