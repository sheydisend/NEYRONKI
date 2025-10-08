from sqlalchemy.orm import Session
from app import models, schemas
from passlib.context import CryptContext
import hashlib
import json

# Используем pbkdf2_sha256 вместо bcrypt
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    default="pbkdf2_sha256",
    pbkdf2_sha256__default_rounds=30000
)

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_id(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def get_preferences_by_user_id(db: Session, user_id: int):
    return db.query(models.UserPreferences).filter(models.UserPreferences.user_id == user_id).first()

def create_user_preferences(db: Session, preferences: schemas.PreferencesCreate, user_id: int):
    # Нормализуем данные перед сохранением
    normalized_categories = [cat.strip().lower() for cat in preferences.preferred_categories] if preferences.preferred_categories else []
    normalized_languages = [lang.strip().lower() for lang in preferences.preferred_languages] if preferences.preferred_languages else []
    
    db_preferences = models.UserPreferences(
        user_id=user_id,
        preferred_categories=json.dumps(normalized_categories, ensure_ascii=False) if normalized_categories else None,
        min_duration_minutes=preferences.min_duration_minutes,
        max_duration_minutes=preferences.max_duration_minutes,
        preferred_languages=json.dumps(normalized_languages, ensure_ascii=False) if normalized_languages else None,
        exclude_explicit_content=preferences.exclude_explicit_content,
        educational_preference=preferences.educational_preference,
        entertainment_preference=preferences.entertainment_preference
    )
    db.add(db_preferences)
    db.commit()
    db.refresh(db_preferences)
    return db_preferences

def update_user_preferences(db: Session, preferences: schemas.PreferencesCreate, user_id: int):
    db_preferences = get_preferences_by_user_id(db, user_id)
    if db_preferences:
        # Нормализуем данные перед сохранением
        normalized_categories = [cat.strip().lower() for cat in preferences.preferred_categories] if preferences.preferred_categories else []
        normalized_languages = [lang.strip().lower() for lang in preferences.preferred_languages] if preferences.preferred_languages else []
        
        db_preferences.preferred_categories = json.dumps(normalized_categories, ensure_ascii=False) if normalized_categories else None
        db_preferences.min_duration_minutes = preferences.min_duration_minutes
        db_preferences.max_duration_minutes = preferences.max_duration_minutes
        db_preferences.preferred_languages = json.dumps(normalized_languages, ensure_ascii=False) if normalized_languages else None
        db_preferences.exclude_explicit_content = preferences.exclude_explicit_content
        db_preferences.educational_preference = preferences.educational_preference
        db_preferences.entertainment_preference = preferences.entertainment_preference
        
        db.commit()
        db.refresh(db_preferences)
    
    return db_preferences

# Функция для преобразования данных из базы в схему Pydantic
def preferences_to_schema(db_preferences):
    if not db_preferences:
        return None
    
    def parse_list(value):
        if not value:
            return []
        try:
            # Пытаемся распарсить как JSON
            return json.loads(value)
        except json.JSONDecodeError:
            # Если это строка с запятыми, разбиваем и нормализуем
            if isinstance(value, str):
                # Убираем квадратные скобки если есть и разбиваем
                clean_value = value.replace('[', '').replace(']', '').replace("'", "").replace('"', '')
                items = [item.strip() for item in clean_value.split(',') if item.strip()]
                # Нормализуем каждый элемент
                return [item for item in items]
            return []
    
    preferred_categories = parse_list(db_preferences.preferred_categories)
    preferred_languages = parse_list(db_preferences.preferred_languages)
    
    return schemas.PreferencesResponse(
        id=db_preferences.id,
        user_id=db_preferences.user_id,
        preferred_categories=preferred_categories,
        min_duration_minutes=db_preferences.min_duration_minutes,
        max_duration_minutes=db_preferences.max_duration_minutes,
        preferred_languages=preferred_languages,
        exclude_explicit_content=db_preferences.exclude_explicit_content,
        educational_preference=db_preferences.educational_preference,
        entertainment_preference=db_preferences.entertainment_preference,
        created_at=db_preferences.created_at,
        updated_at=db_preferences.updated_at
    )