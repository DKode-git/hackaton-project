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

# Auth Models
class UserAuth(BaseModel):
    username: Optional[str] = None 
    password: str
    email: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str

# Fitness Models
class HydrationUpdate(BaseModel):
    user_id: str
    hydration: int

class Set(BaseModel):
    kg: float
    reps: int
    completed: bool

class Exercise(BaseModel):
    name: str
    sets: List[Set]

class WorkoutSession(BaseModel):
    user_id: str
    duration_seconds: int
    exercises: List[Exercise]
    date: Optional[str] = None

# AI & Feedback Models
class AIRefineRequest(BaseModel):
    text: str

class FeedbackSubmission(BaseModel):
    content: str
    category: str
    priority: str

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

def get_workouts_db(): return load_json(WORKOUTS_FILE, [])
def save_workout_entry(entry):
    data = get_workouts_db()
    data.append(entry)
    save_json(WORKOUTS_FILE, data)

def get_feedback_db(): return load_json(FEEDBACK_FILE, [])
def save_feedback_entry(entry):
    data = get_feedback_db()
    data.append(entry)
    save_json(FEEDBACK_FILE, data)

# --- 4. AUTHENTICATION ENDPOINTS (Hybrid Support) ---

# A. Standard Hackathon Auth (Root Level)
@app.post("/login")
def root_login(creds: LoginRequest):
    db = get_db()
    # Check if user exists
    user = next((u for u in db['users'] if u['username'] == creds.username), None)
    
    if user and user['password'] == creds.password:
        return {
            "token": "hackathon-demo-token-xyz",
            "username": user['username']
        }
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/register")
def root_register(creds: RegisterRequest):
    db = get_db()
    if any(u['username'] == creds.username for u in db['users']):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    new_user = {
        "user_id": f"user_{uuid.uuid4().hex[:8]}",
        "username": creds.username,
        "email": f"{creds.username}@example.com", # Auto-gen email for root register
        "password": creds.password,
        "stats": { "steps": 0, "stepGoal": 10000, "calories": 0, "calGoal": 2500, "hydration": 0 }
    }
    db['users'].append(new_user)
    save_db(db)
    return {"message": "Account created successfully"}

@app.get("/verify_token")
def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Token")
    # For demo, any token starting with 'Bearer ' is valid
    return {"valid": True}

@app.post("/logout")
def logout():
    return {"message": "Logged out"}

# B. Existing API V1 Auth (Keep for backward compatibility)
@app.post("/api/v1/auth/register")
def v1_register(user: UserAuth):
    if not user.username: raise HTTPException(status_code=400, detail="Username required")
    db = get_db()
    if any(u['email'] == user.email for u in db['users']):
        raise HTTPException(status_code=400, detail="User exists")
    
    new_user = {
        "user_id": f"user_{uuid.uuid4().hex[:8]}",
        "username": user.username,
        "email": user.email,
        "password": user.password,
        "stats": { "steps": 0, "stepGoal": 10000, "calories": 0, "calGoal": 2500, "hydration": 0 }
    }
    db['users'].append(new_user)
    save_db(db)
    return {"status": "success", "message": "Identity created"}

@app.post("/api/v1/auth/login")
def v1_login(user: UserAuth):
    db = get_db()
    login_id = user.email or user.username
    found = next((u for u in db['users'] if u['email'] == login_id or u['username'] == login_id), None)
    if found and found['password'] == user.password:
        return { "status": "success", "user_id": found['user_id'], "username": found['username'], "token": "demo-token-123" }
    raise HTTPException(status_code=401, detail="Invalid credentials")

# --- 5. FITNESS DASHBOARD ENDPOINTS ---

@app.get("/api/v1/user/daily-stats")
def get_stats(user_id: str):
    db = get_db()
    user = next((u for u in db['users'] if u['user_id'] == user_id), None)
    if not user: raise HTTPException(status_code=404, detail="User not found")
    user['stats']['steps'] = random.randint(2000, 12000) 
    user['stats']['calories'] = int(user['stats']['steps'] * 0.05)
    return user['stats']

@app.patch("/api/v1/user/hydrate")
def update_hydration(update: HydrationUpdate):
    db = get_db()
    user = next((u for u in db['users'] if u['user_id'] == update.user_id), None)
    if not user: raise HTTPException(status_code=404, detail="User not found")
    user['stats']['hydration'] = update.hydration
    save_db(db)
    return {"status": "updated", "level": update.hydration}

@app.post("/api/v1/workout/save")
def save_workout(workout: WorkoutSession):
    entry = {
        "id": f"wo_{uuid.uuid4().hex[:8]}",
        "user_id": workout.user_id,
        "date": workout.date or datetime.now().isoformat(),
        "duration": workout.duration_seconds,
        "exercises": [ex.dict() for ex in workout.exercises]
    }
    save_workout_entry(entry)
    return {"status": "success", "workout_id": entry["id"]}

EXERCISE_DB = [ "Bench Press", "Squat", "Deadlift", "Pull Up", "Overhead Press", "Bicep Curl", "Tricep Pushdown" ]

@app.get("/api/v1/exercises/search")
def search_exercises(q: str = ""):
    if not q: return EXERCISE_DB
    return [ex for ex in EXERCISE_DB if q.lower() in ex.lower()]

@app.get("/api/v1/analytics/history")
def get_history(user_id: str):
    all_workouts = get_workouts_db()
    user_workouts = [w for w in all_workouts if w.get('user_id') == user_id]
    total_volume = sum(sum(s['kg'] * s['reps'] for ex in w['exercises'] for s in ex['sets']) for w in user_workouts)
    
    chart_data = [12000, 15000, 11000, 18000, 20000, 24000]
    if total_volume > 0: chart_data.append(total_volume)
    
    return {
        "summary": { "total_workouts": len(user_workouts) + 42, "avg_duration": "45m", "total_volume": f"{int((total_volume+150000)/1000)}k", "prs": 12 },
        "chart": { "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Now"], "data": chart_data },
        "heatmap": [random.choice([0, 1, 2, 3]) for _ in range(365)]
    }

# --- 6. AI & SYSTEM ENDPOINTS (NEW) ---

@app.post("/v1/ai/refine")
def ai_refine(payload: AIRefineRequest):
    """
    Simulates an AI polishing text.
    In a real app, this would call OpenAI. 
    Here, it makes the text sound 'Professional'.
    """
    time.sleep(0.8) # Fake latency for realism
    
    raw = payload.text
    # Simple Mock Logic
    polished = f"Regarding your input, we have optimized the following: {raw}. Furthermore, strategic implementation is advised."
    
    if "bug" in raw.lower():
        polished = f"Issue Identified: {raw}. Priority: High. Recommended Action: Immediate investigation required."
    elif "feature" in raw.lower():
        polished = f"Proposal: {raw}. Business Value: Moderate. Status: Added to backlog for Q3 review."
        
    return {"text": polished}

@app.post("/v1/dispatch/feedback")
def dispatch_feedback(item: FeedbackSubmission):
    """Saves feedback to the persistent JSON store."""
    entry = {
        "id": uuid.uuid4().hex[:6],
        "status": "pending",
        "category": item.category,
        "text": item.content,
        "summary": item.content[:30] + "..." if len(item.content) > 30 else item.content,
        "sentiment": random.randint(60, 95), # Mock sentiment analysis
        "priority": item.priority,
        "date": "Just now"
    }
    save_feedback_entry(entry)
    return {"status": "success", "message": "Feedback dispatched successfully."}

@app.get("/v1/system/templates")
def get_templates():
    return [
        {"id": "t1", "label": "Report Bug", "icon": "fa-bug"},
        {"id": "t2", "label": "Feature Request", "icon": "fa-lightbulb"},
        {"id": "t3", "label": "UX Improvement", "icon": "fa-paint-brush"},
        {"id": "t4", "label": "Performance", "icon": "fa-tachometer-alt"}
    ]

# --- 7. FEEDBACK DASHBOARD ENDPOINTS ---

@app.get("/suggestions")
def get_suggestions():
    """Returns real feedback from disk + some mock items for the demo."""
    real_data = get_feedback_db()
    
    # Mock Data (Always ensure the list isn't empty for the demo)
    mock_data = [
        {"id": 1, "status": "pending", "category": "Feature Request", "text": "Dark mode for charts.", "summary": "Chart Dark Mode", "sentiment": 65, "date": "2h ago"},
        {"id": 2, "status": "approved", "category": "Bug Report", "text": "Hydration counter resets.", "summary": "Hydration Bug", "sentiment": 30, "date": "5h ago"}
    ]
    
    # Combine real submissions with mocks (Real first)
    return real_data[::-1] + mock_data

@app.get("/stats/trends")
def get_trends():
    return {
        "average_sentiment": random.randint(70, 95),
        "top_keyword": random.choice(["Performance", "Dark Mode", "Sync", "Battery"]),
        "urgent_count": random.randint(1, 5)
    }

if __name__ == "__main__":
    import uvicorn
    # Runs on port 8000 to match frontend
    uvicorn.run(app, host="0.0.0.0", port=8000)