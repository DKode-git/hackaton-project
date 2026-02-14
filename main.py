import json
import os
import uuid
import random
import time
from typing import List, Optional, Any
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Hackton Integrated Backend")

# --- 1. CONFIGURATION & FILE SYSTEM ---
DB_FILE = "users.json"
FEEDBACK_FILE = "feedback.json"

# CORS: Allow all for local Hackathon development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. DATA MODELS ---

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str

class FeedbackSubmission(BaseModel):
    text: str          # Aligned with Frontend Contract
    category: str
    priority: Optional[str] = "normal"

class FeedbackUpdate(BaseModel):
    status: str

class PolishRequest(BaseModel):
    text: str

# --- 3. DATABASE ENGINE ---

def load_json(filename, default):
    if not os.path.exists(filename):
        with open(filename, "w") as f: json.dump(default, f)
        return default
    try:
        with open(filename, "r") as f: return json.load(f)
    except:
        return default

def save_json(filename, data):
    with open(filename, "w") as f: json.dump(data, f, indent=4)

def get_db(): return load_json(DB_FILE, {"users": []})
def save_db(data): save_json(DB_FILE, data)

def get_feedback_db(): return load_json(FEEDBACK_FILE, [])
def save_feedback_entry(entry):
    data = get_feedback_db()
    data.append(entry)
    save_json(FEEDBACK_FILE, data)

def update_feedback_status_in_db(item_id, new_status):
    data = get_feedback_db()
    updated = False
    for item in data:
        if str(item.get("id")) == str(item_id):
            item["status"] = new_status
            updated = True
            break
    if updated:
        save_json(FEEDBACK_FILE, data)
    return updated

# --- 4. AUTHENTICATION ENDPOINTS ---

@app.post("/login")
def root_login(creds: LoginRequest):
    db = get_db()
    # Find user
    user = next((u for u in db['users'] if u['username'] == creds.username), None)
    
    # Pre-seed admin if database is empty or user not found, for Hackathon ease
    if not user and creds.username == "admin" and creds.password == "password":
        return {
            "token": "admin-token-123",
            "username": "admin",
            "role": "admin",
            "user_id": "admin_01"
        }

    if user and user['password'] == creds.password:
        return {
            "token": f"bearer-token-{uuid.uuid4()}",
            "username": user['username'],
            "role": user.get('role', 'user'), # Critical for Routing
            "user_id": user['user_id']
        }
    raise HTTPException(status_code=401, detail="Invalid username or password")

@app.post("/register")
def root_register(creds: RegisterRequest):
    db = get_db()
    if any(u['username'] == creds.username for u in db['users']):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    new_user = {
        "user_id": f"user_{uuid.uuid4().hex[:8]}",
        "username": creds.username,
        "password": creds.password, 
        "role": "user",
        "stats": { "steps": 0, "hydration": 0 }
    }
    db['users'].append(new_user)
    save_db(db)
    return {"message": "Account created successfully"}

# --- 5. DASHBOARD ENDPOINTS ---

@app.get("/suggestions")
def get_suggestions(authorization: Optional[str] = Header(None)):
    """Returns real feedback from disk + mock items."""
    real_data = get_feedback_db()
    
    # Mock Data (Ensures the dashboard is never empty during demo)
    mock_data = [
        {"id": 1, "status": "pending", "category": "Facilities", "text": "We need better coffee.", "ai_summary": "Beverage request", "sentiment": 45, "owner": "user"},
        {"id": 2, "status": "approved", "category": "HR", "text": "4-day work week proposal.", "ai_summary": "Schedule change", "sentiment": 90, "owner": "admin"},
    ]
    
    # In a real app, we would filter by Authorization header here
    # For Hackathon, we return everything + mocks
    combined = real_data + mock_data
    return combined

@app.post("/suggestions")
def create_suggestion(item: FeedbackSubmission, authorization: Optional[str] = Header(None)):
    # Simulate AI processing
    ai_sentiment = random.randint(60, 100)
    
    entry = {
        "id": uuid.uuid4().hex[:8],
        "status": "pending",
        "category": item.category,
        "text": item.text,
        "ai_summary": f"AI Summary: {item.text[:20]}...",
        "sentiment": ai_sentiment,
        "priority": item.priority,
        "owner": "current_user", # Simplified
        "date": str(datetime.now().date()) if 'datetime' in globals() else "Just now"
    }
    save_feedback_entry(entry)
    return entry

@app.patch("/suggestions/{item_id}")
def update_suggestion(item_id: str, update: FeedbackUpdate):
    """Updates the status of a suggestion."""
    success = update_feedback_status_in_db(item_id, update.status)
    if success:
        return {"status": "success", "id": item_id, "new_status": update.status}
    
    # If not found in DB, it might be a mock item. Return success for UI fluidity.
    return {"status": "success", "id": item_id, "message": "Mock item updated in memory"}

# --- 6. AI ENDPOINTS ---

@app.post("/ai/polish")
def ai_refine(payload: PolishRequest):
    """
    Mock AI Endpoint. 
    Matches the frontend contract: POST /ai/polish { text: "..." }
    """
    time.sleep(0.5)  # "Physics" delay
    
    raw = payload.text
    polished = raw.capitalize()
    
    if "wifi" in raw.lower():
        polished = "The network infrastructure requires immediate diagnostic attention."
    elif len(raw) < 10:
        polished = f"Elaborated: {raw} is a valid point that requires further discussion."
    else:
        polished = f"✨ Professional Edit: {raw} (Optimized for clarity)"

    return {"polished": polished}

if __name__ == "__main__":
    import uvicorn
    # Run on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)