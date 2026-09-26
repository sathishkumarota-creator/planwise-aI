from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr

class RegisterUser(BaseModel):
    username: str
    email: str
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
