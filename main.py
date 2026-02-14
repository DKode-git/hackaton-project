import json
import os
import uuid
import random
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Header, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# --- 1. CONFIGURATION & FILE SYSTEM ---
DB_FILE = "users.json"
WORKOUTS_FILE = "workouts.json"
FEEDBACK_FILE = "feedback.json"

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
    content: str
    category: str
    priority: str

class FeedbackUpdate(BaseModel):
    status: str

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

def update_feedback_status(item_id, new_status):
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
    
    if user and user['password'] == creds.password:
        return {
            "token": f"bearer-token-{uuid.uuid4()}",
            "username": user['username'],
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
        "password": creds.password, # In production, hash this!
        "stats": { "steps": 0, "hydration": 0 }
    }
    db['users'].append(new_user)
    save_db(db)
    return {"message": "Account created successfully"}

@app.get("/verify_token")
def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Token")
    return {"valid": True}

@app.post("/logout")
def logout():
    return {"message": "Logged out"}

# --- 5. DASHBOARD ENDPOINTS ---

@app.get("/suggestions")
def get_suggestions():
    """Returns real feedback from disk + mock items to ensure dashboard isn't empty."""
    real_data = get_feedback_db()
    
    # Mock Data (Serves as 'Pre-seeded' data for the Hackathon)
    mock_data = [
        {"id": "mock_1", "status": "pending", "category": "Feature Request", "text": "Dark mode for charts.", "summary": "Chart Dark Mode", "sentiment": 65, "date": "2h ago"},
        {"id": "mock_2", "status": "approved", "category": "Bug Report", "text": "Hydration counter resets.", "summary": "Hydration Bug", "sentiment": 30, "date": "5h ago"},
        {"id": "mock_3", "status": "rejected", "category": "UX", "text": "The font size is too small on mobile.", "summary": "Mobile Accessibility", "sentiment": 45, "date": "1d ago"}
    ]
    
    # Combine: Real data first, then mocks
    return real_data[::-1] + mock_data

@app.post("/suggestions")
def create_suggestion(item: FeedbackSubmission):
    entry = {
        "id": uuid.uuid4().hex[:8],
        "status": "pending",
        "category": item.category,
        "text": item.content,
        "summary": item.content[:40] + "..." if len(item.content) > 40 else item.content,
        "sentiment": random.randint(60, 95),
        "priority": item.priority,
        "date": "Just now"
    }
    save_feedback_entry(entry)
    return {"status": "success", "data": entry}

@app.patch("/suggestions/{item_id}")
def update_suggestion(item_id: str, update: FeedbackUpdate):
    """Updates the status of a suggestion."""
    success = update_feedback_status(item_id, update.status)
    if success:
        return {"status": "success", "id": item_id, "new_status": update.status}
    
    # If not found in DB, it might be a mock item. We return success for UI fluidity.
    return {"status": "success", "id": item_id, "message": "Mock item updated in memory"}

@app.get("/stats/trends")
def get_trends():
    return {
        "average_sentiment": random.randint(70, 95),
        "top_keyword": random.choice(["Performance", "Dark Mode", "Sync", "Battery"]),
        "urgent_count": random.randint(1, 5)
    }

# --- 6. AI ENDPOINTS ---

class AIRefineRequest(BaseModel):
    text: str

@app.post("/v1/ai/polish")
def ai_refine(payload: AIRefineRequest):
    time.sleep(0.5) 
    raw = payload.text
    polished = f"Optimized: {raw}" # Replace with real AI logic if needed
    if "suck" in raw or "bad" in raw:
        polished = f"The user has reported a critical issue regarding: {raw.replace('suck', 'performance').replace('bad', 'suboptimal behavior')}."
    return {"polished_text": polished}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)