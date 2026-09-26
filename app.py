import os
import json
import re
import uuid
import shutil
import asyncio
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Union
from io import BytesIO
from PIL import Image

from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form, Request, status, Cookie
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
import bcrypt
from jose import JWTError, jwt
from dotenv import load_dotenv

import gemini_utils

# Load environment variables
load_dotenv()

# App initialization
app = FastAPI(title="PocketSmart: AI Budget Planner")

SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_pocketsmart_2026")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Password hashing helper compatible with passlib / bcrypt
class PasswordContext:
    def hash(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8")[:72], salt).decode("utf-8")

    def verify(self, password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("utf-8"))
        except Exception:
            return False

pwd_context = PasswordContext()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
os.makedirs("static/uploads", exist_ok=True)
os.makedirs("static/images", exist_ok=True)
os.makedirs("data", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def render_template(request: Request, name: str, context: dict = None):
    if context is None:
        context = {}
    return templates.TemplateResponse(request=request, name=name, context=context)

# Models
class RegisterUser(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    password: str

class UserInDB(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    hashed_password: str
    disabled: bool = False

class Token(BaseModel):
    access_token: str
    token_type: str

class UserSession:
    def __init__(self, username: str, token: str):
        self.username = username
        self.token = token
        self.login_time = datetime.now(timezone.utc)
        self.last_activity = datetime.now(timezone.utc)
        self.user_data: Dict[str, Any] = {}

class RecommendationItem:
    def __init__(self, item_id: str, username: str, rec_type: str, input_summary: dict, result: dict):
        self.id = item_id
        self.username = username
        self.timestamp = datetime.now(timezone.utc).strftime("%b %d, %Y, %I:%M %p")
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.recommendation_type = rec_type
        self.input_summary = input_summary
        self.full_result = result
        self.result_summary = {
            "total_budget": result.get("total_budget", 0),
            "remaining_budget": result.get("remaining_budget", 0),
            "categories_count": len(result.get("budget_breakdown", [])) or len(result.get("jewelry_recommendations", []))
        }

class HomeBudgetInput(BaseModel):
    total_budget: float
    num_lights: int = 0
    num_fans: int = 0
    num_furniture: int = 0
    num_dining_tables: int = 0
    has_living_room: bool = False
    has_kitchen: bool = False
    has_bedroom: bool = False
    additional_requirements: Optional[str] = "None"

class PartyBudgetInput(BaseModel):
    total_budget: float
    num_guests: int
    party_type: str
    venue_type: Optional[str] = "Not Specified"
    needs_catering: bool = True
    needs_decoration: bool = True
    needs_entertainment: bool = True
    additional_requirements: Optional[str] = "None"

class JewelryBudgetInput(BaseModel):
    total_budget: float
    occasion: str
    preferences: Optional[str] = "Not specified"

# In-Memory & Persistent Storage
DB_FILE = "data/database.json"

users_db: Dict[str, UserInDB] = {}
active_sessions: Dict[str, UserSession] = {}
blacklisted_tokens = set()
user_recommendations: Dict[str, List[RecommendationItem]] = {}

def load_persistence():
    global users_db, user_recommendations
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for uname, udata in saved.get("users", {}).items():
                    users_db[uname] = UserInDB(**udata)
                for uname, recs in saved.get("recommendations", {}).items():
                    user_recommendations[uname] = []
                    for r in recs:
                        item = RecommendationItem(
                            item_id=r["id"],
                            username=r["username"],
                            rec_type=r["recommendation_type"],
                            input_summary=r["input_summary"],
                            result=r["full_result"]
                        )
                        item.timestamp = r.get("timestamp", item.timestamp)
                        item.created_at = r.get("created_at", item.created_at)
                        item.result_summary = r.get("result_summary", item.result_summary)
                        user_recommendations[uname].append(item)
        except Exception as e:
            print(f"Error loading persistent database: {e}")

    # Seed default user 'sai' if not exists (as seen in document screenshots)
    if "sai" not in users_db:
        users_db["sai"] = UserInDB(
            username="sai",
            email="sai@pocketsmart.ai",
            full_name="Sai Kumar",
            hashed_password=pwd_context.hash("password123")
        )
        # Prepopulate demo history as seen on page 31 & 38 of PDF
        if "sai" not in user_recommendations:
            user_recommendations["sai"] = [
                RecommendationItem(
                    item_id=str(uuid.uuid4())[:8],
                    username="sai",
                    rec_type="jewelry",
                    input_summary={"total_budget": 5000.0, "occasion": "Birthday", "has_image": True},
                    result=gemini_utils.generate_fallback_jewelry_recommendations(
                        JewelryBudgetInput(total_budget=5000.0, occasion="Birthday", preferences="Casual & modern")
                    )
                ),
                RecommendationItem(
                    item_id=str(uuid.uuid4())[:8],
                    username="sai",
                    rec_type="party",
                    input_summary={"total_budget": 5000.0, "party_type": "Wedding", "guests": 3, "needs": ["catering", "entertainment"]},
                    result=gemini_utils.generate_fallback_party_recommendations(
                        PartyBudgetInput(total_budget=5000.0, num_guests=3, party_type="Wedding", venue_type="Home")
                    )
                ),
                RecommendationItem(
                    item_id=str(uuid.uuid4())[:8],
                    username="sai",
                    rec_type="home",
                    input_summary={"total_budget": 5000.0, "rooms": ["Living Room", "Kitchen"], "lights": 5, "fans": 4, "furniture": 2},
                    result=gemini_utils.generate_fallback_home_recommendations(
                        HomeBudgetInput(total_budget=5000.0, num_lights=5, num_fans=4, num_furniture=2, num_dining_tables=1)
                    )
                )
            ]
            save_persistence()

def save_persistence():
    try:
        data = {
            "users": {u: users_db[u].model_dump() for u in users_db},
            "recommendations": {}
        }
        for u, recs in user_recommendations.items():
            data["recommendations"][u] = [
                {
                    "id": r.id,
                    "username": r.username,
                    "timestamp": r.timestamp,
                    "created_at": r.created_at,
                    "recommendation_type": r.recommendation_type,
                    "input_summary": r.input_summary,
                    "full_result": r.full_result,
                    "result_summary": r.result_summary
                }
                for r in recs
            ]
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving database: {e}")

load_persistence()

# Auth Utilities
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_token_from_request(request: Request) -> Optional[str]:
    # Check Authorization header
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth.split(" ")[1]
    # Check Cookie
    token = request.cookies.get("access_token")
    if token:
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
        return token
    return None

async def get_current_user_optional(request: Request) -> Optional[UserInDB]:
    token = await get_token_from_request(request)
    if not token or token in blacklisted_tokens:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = users_db.get(username)
        return user
    except JWTError:
        return None

async def get_current_active_user(request: Request) -> UserInDB:
    user = await get_current_user_optional(request)
    if not user:
        # Check if requesting HTML page or API
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            # Redirect to login
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/login"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user

def save_to_history(username: str, recommendation_type: str, input_data: dict, result: dict):
    if username not in user_recommendations:
        user_recommendations[username] = []
    
    rec_item = RecommendationItem(
        item_id=str(uuid.uuid4())[:8],
        username=username,
        rec_type=recommendation_type,
        input_summary=input_data,
        result=result
    )
    user_recommendations[username].insert(0, rec_item)
    save_persistence()
    return rec_item

def save_upload_file(upload_file: UploadFile) -> str:
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{upload_file.filename}"
    file_path = os.path.join("static", "uploads", filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return file_path

# ================= ROUTES =================

# 1. Landing & Marketing Pages
@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    user = await get_current_user_optional(request)
    return render_template(request, "index.html", {"user": user})

# 2. Authentication Pages & Handlers
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = await get_current_user_optional(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return render_template(request, "login.html", {"error": None})

@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    user = users_db.get(username)
    if not user or not pwd_context.verify(password, user.hashed_password):
        return render_template(request, "login.html", {"error": "Invalid username or password"})
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    
    # Store session
    session = UserSession(username=user.username, token=token)
    active_sessions[user.username] = session
    
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    user = await get_current_user_optional(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return render_template(request, "register.html", {"error": None})

@app.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    if password != confirm_password:
        return render_template(request, "register.html", {"error": "Passwords do not match."})
    
    if username in users_db:
        return render_template(request, "register.html", {"error": "Username already registered."})
    
    hashed_pwd = pwd_context.hash(password)
    new_user = UserInDB(
        username=username,
        email=email,
        full_name=username.capitalize(),
        hashed_password=hashed_pwd
    )
    users_db[username] = new_user
    save_persistence()
    
    # Auto-login
    token = create_access_token(data={"sub": username})
    active_sessions[username] = UserSession(username=username, token=token)
    
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return response

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_db.get(form_data.username)
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    
    # Session update
    active_sessions[user.username] = UserSession(username=user.username, token=access_token)
    
    response = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return response

@app.get("/logout")
@app.post("/logout")
async def logout(request: Request):
    token = await get_token_from_request(request)
    if token:
        blacklisted_tokens.add(token)
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username and username in active_sessions:
                del active_sessions[username]
        except JWTError:
            pass
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response

# 3. User Dashboard
@app.get("/dashboard", response_class=HTMLResponse)
async def user_dashboard(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    user_recs = user_recommendations.get(current_user.username, [])[:5]
    return render_template(request, "dashboard.html", {
        "user": current_user,
        "recent_activities": user_recs
    })

# 4. Session Info Endpoints
@app.get("/session-info")
async def get_session_info(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    """Retrieve metadata about the current user session."""
    session = active_sessions.get(current_user.username)
    if session:
        return {
            "username": session.username,
            "login_time": session.login_time.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "session_duration_minutes": int((datetime.now(timezone.utc) - session.login_time).total_seconds() // 60),
            "user_data": session.user_data
        }
    return {
        "username": current_user.username,
        "login_time": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat(),
        "session_duration_minutes": 0,
        "user_data": {}
    }

@app.post("/session-data")
async def update_session_data(data: Dict[str, Any], current_user: UserInDB = Depends(get_current_active_user)):
    session = active_sessions.get(current_user.username)
    if session:
        session.user_data.update(data)
        session.last_activity = datetime.now(timezone.utc)
        return {"message": "Session data updated", "data": session.user_data}
    raise HTTPException(status_code=404, detail="No active session found")

# 5. Home Interior Planner
@app.get("/home-planner", response_class=HTMLResponse)
async def home_planner_page(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    return render_template(request, "home_planner.html", {"user": current_user})

@app.post("/home-budget")
@app.post("/generate-home")
async def plan_home_budget(budget_input: HomeBudgetInput, request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    """Generate home budget recommendations and save to session/history."""
    if current_user.username in active_sessions:
        active_sessions[current_user.username].user_data["last_home_budget"] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "budget": budget_input.total_budget,
            "requirements": {
                "lights": budget_input.num_lights,
                "fans": budget_input.num_fans,
                "furniture": budget_input.num_furniture,
                "dining_tables": budget_input.num_dining_tables
            }
        }

    result = gemini_utils.get_home_recommendations(budget_input)
    
    save_to_history(
        username=current_user.username,
        recommendation_type="home",
        input_data=budget_input.model_dump(),
        result=result
    )
    return result

# 6. Party Budget Planner
@app.get("/party-planner", response_class=HTMLResponse)
async def party_planner_page(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    return render_template(request, "party_planner.html", {"user": current_user})

@app.post("/party-budget")
@app.post("/generate-party")
async def plan_party_budget(budget_input: PartyBudgetInput, request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    """Generate party planning recommendations and save to history."""
    if current_user.username in active_sessions:
        active_sessions[current_user.username].user_data["last_party_budget"] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "budget": budget_input.total_budget,
            "party_type": budget_input.party_type,
            "guests": budget_input.num_guests
        }

    result = gemini_utils.get_party_recommendations(budget_input)
    
    save_to_history(
        username=current_user.username,
        recommendation_type="party",
        input_data=budget_input.model_dump(),
        result=result
    )
    return result

# 7. Jewelry Budget Planner
@app.get("/jewelry-planner", response_class=HTMLResponse)
async def jewelry_planner_page(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    return render_template(request, "jewelry_planner.html", {"user": current_user})

@app.post("/jewelry-budget")
@app.post("/generate-jewelry")
async def plan_jewelry_budget(
    total_budget: float = Form(...),
    occasion: str = Form(...),
    preferences: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Generate jewelry budget recommendations with optional outfit image analysis."""
    budget_input = JewelryBudgetInput(
        total_budget=total_budget,
        occasion=occasion,
        preferences=preferences or "Not specified"
    )

    image_path = None
    image_filename = None
    if image and image.filename:
        image_path = save_upload_file(image)
        image_filename = os.path.basename(image_path)

    if current_user.username in active_sessions:
        active_sessions[current_user.username].user_data["last_jewelry_budget"] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "budget": budget_input.total_budget,
            "occasion": budget_input.occasion,
            "has_image": image_path is not None
        }

    result = gemini_utils.get_jewelry_recommendations(budget_input, image_path)
    
    input_data = budget_input.model_dump()
    if image_filename:
        input_data["image"] = image_filename

    save_to_history(
        username=current_user.username,
        recommendation_type="jewelry",
        input_data=input_data,
        result=result
    )
    return result

# 8. History & Detailed Recommendations
@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, current_user: UserInDB = Depends(get_current_active_user)):
    """History page to view past recommendations."""
    items = user_recommendations.get(current_user.username, [])
    return render_template(request, "history.html", {
        "user": current_user,
        "recommendations": items
    })

@app.get("/recommendation-history")
async def get_recommendation_history(current_user: UserInDB = Depends(get_current_active_user)):
    """API endpoint to get list of past recommendations."""
    history = user_recommendations.get(current_user.username, [])
    history_data = []
    for item in history:
        history_data.append({
            "id": item.id,
            "timestamp": item.timestamp,
            "type": item.recommendation_type,
            "input": item.input_summary,
            "summary": item.result_summary
        })
    return {"history": history_data}

@app.get("/recommendation-details/{recommendation_id}")
async def get_recommendation_details(recommendation_id: str, current_user: UserInDB = Depends(get_current_active_user)):
    """API endpoint returning full details for a specific saved recommendation."""
    history = user_recommendations.get(current_user.username, [])
    for item in history:
        if item.id == recommendation_id:
            return {
                "id": item.id,
                "timestamp": item.timestamp,
                "type": item.recommendation_type,
                "input": item.input_summary,
                "full_result": item.full_result
            }
    raise HTTPException(status_code=404, detail="Recommendation not found")

# 9. Startup & Cleanup Background Task
@app.on_event("startup")
async def setup_session_cleanup():
    async def cleanup_expired_sessions():
        while True:
            current_time = datetime.now(timezone.utc)
            expired_sessions = [
                uname for uname, session in active_sessions.items()
                if (current_time - session.last_activity).total_seconds() > 1800
            ]
            for uname in expired_sessions:
                print(f"[Session] Removing expired session for {uname}")
                del active_sessions[uname]
            await asyncio.sleep(300)
    asyncio.create_task(cleanup_expired_sessions())

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting PocketSmart: AI Budget Planner on http://localhost:{port} ...")
    uvicorn.run("app:app", host=host, port=port, reload=True)
