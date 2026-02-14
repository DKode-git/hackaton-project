import json
import os
import uuid
import random
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# --- 1. CONFIGURATION ---
DB_FILE = "users.json"
WORKOUTS_FILE = "workouts.json"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. DATA MODELS ---

class UserAuth(BaseModel):
    # FIXED: Made username optional so Login (which only sends email) doesn't fail validation
    username: Optional[str] = None 
    password: str
    email: Optional[str] = None

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

# --- 3. DATABASE ENGINE ---

def get_db():
    """Reads users.json safely."""
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f: json.dump({"users": []}, f)
        return {"users": []}
    try:
        with open(DB_FILE, "r") as f: return json.load(f)
    except:
        return {"users": []}

def save_db(data):
    """Writes to users.json."""
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_workouts_db():
    if not os.path.exists(WORKOUTS_FILE):
        with open(WORKOUTS_FILE, "w") as f: json.dump([], f)
        return []
    try:
        with open(WORKOUTS_FILE, "r") as f: return json.load(f)
    except:
        return []

def save_workout_entry(entry):
    data = get_workouts_db()
    data.append(entry)
    with open(WORKOUTS_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- 4. AUTH ENDPOINTS ---

@app.post("/api/v1/auth/register")
def register(user: UserAuth):
    # For register, we require a username.
    if not user.username:
          raise HTTPException(status_code=400, detail="Username is required for registration")

    db = get_db()
    
    # Check duplicate
    if any(u['email'] == user.email for u in db['users']):
        raise HTTPException(status_code=400, detail="User already exists")

    # Initialize User with Defaults
    new_user = {
        "user_id": f"user_{uuid.uuid4().hex[:8]}",
        "username": user.username,
        "email": user.email,
        "password": user.password,
        "stats": {
            "steps": 0,
            "stepGoal": 10000,
            "calories": 0,
            "calGoal": 2500,
            "hydration": 0
        }
    }
    
    db['users'].append(new_user)
    save_db(db)
    
    return {"status": "success", "message": "Identity created"}

@app.post("/api/v1/auth/login")
def login(user: UserAuth):
    db = get_db()
    
    # FIXED: Allow login via Email OR Username
    login_id = user.email or user.username
    
    if not login_id:
        raise HTTPException(status_code=400, detail="Email or Username required")

    # Find User
    found_user = next((u for u in db['users'] if u['email'] == login_id or u['username'] == login_id), None)
    
    if found_user and found_user['password'] == user.password:
        return {
            "status": "success",
            "user_id": found_user['user_id'],
            "username": found_user['username'],
            "token": "demo-token-123" 
        }
    
    raise HTTPException(status_code=401, detail="Invalid credentials")

# --- 5. DASHBOARD ENDPOINTS ---

@app.get("/api/v1/user/daily-stats")
def get_stats(user_id: str):
    db = get_db()
    user = next((u for u in db['users'] if u['user_id'] == user_id), None)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user['stats']['steps'] = random.randint(2000, 12000) 
    user['stats']['calories'] = int(user['stats']['steps'] * 0.05)
    
    return user['stats']

@app.patch("/api/v1/user/hydrate")
def update_hydration(update: HydrationUpdate):
    db = get_db()
    user = next((u for u in db['users'] if u['user_id'] == update.user_id), None)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user['stats']['hydration'] = update.hydration
    save_db(db)
    
    return {"status": "updated", "level": update.hydration}

# --- 6. WORKOUT ENDPOINTS ---

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

EXERCISE_DB = [
    "Bench Press", "Incline Dumbbell Press", "Cable Fly", 
    "Squat", "Leg Press", "Bulgarian Split Squat",
    "Deadlift", "Pull Up", "Lat Pulldown", "Dumbbell Row",
    "Overhead Press", "Lateral Raise", "Face Pull",
    "Bicep Curl", "Hammer Curl", "Tricep Pushdown", "Skullcrusher"
]

@app.get("/api/v1/exercises/search")
def search_exercises(q: str = ""):
    if not q: return EXERCISE_DB
    return [ex for ex in EXERCISE_DB if q.lower() in ex.lower()]

# --- 7. ANALYTICS ENDPOINTS ---

@app.get("/api/v1/analytics/history")
def get_history(user_id: str):
    all_workouts = get_workouts_db()
    user_workouts = [w for w in all_workouts if w.get('user_id') == user_id]
    
    total_volume = 0
    for w in user_workouts:
        for ex in w['exercises']:
            for s in ex['sets']:
                total_volume += (s['kg'] * s['reps'])

    chart_data = [12000, 15000, 11000, 18000, 20000, 24000]
    if total_volume > 0:
        chart_data.append(total_volume) 
    
    heatmap = [random.choice([0, 1, 2, 3]) for _ in range(365)]
    
    return {
        "summary": {
            "total_workouts": len(user_workouts) + 42, 
            "avg_duration": "45m",
            "total_volume": f"{int((total_volume + 150000)/1000)}k",
            "prs": 12
        },
        "chart": {
            "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Now"],
            "data": chart_data
        },
        "heatmap": heatmap
    }

# --- 8. NEW FEEDBACK & TRENDS ENDPOINTS (Request Implementation) ---

@app.get("/suggestions")
def get_suggestions():
    """Returns list of feedback items (Mocked for Hackathon Demo)."""
    return [
        {
            "id": 1,
            "status": "pending",
            "category": "Feature Request",
            "text": "Add a dark mode toggle specifically for the charts.",
            "summary": "Chart Dark Mode",
            "sentiment": 65,
            "date": "2h ago"
        },
        {
            "id": 2,
            "status": "approved",
            "category": "Bug Report",
            "text": "The hydration counter resets if I refresh the page too quickly.",
            "summary": "Hydration Persistence Bug",
            "sentiment": 30,
            "date": "5h ago"
        },
        {
            "id": 3,
            "status": "rejected",
            "category": "UI/UX",
            "text": "Make the font size smaller on mobile devices.",
            "summary": "Mobile Font Adjustment",
            "sentiment": 80,
            "date": "1d ago"
        }
    ]

@app.get("/stats/trends")
def get_trends():
    """Returns high-level dashboard metrics."""
    return {
        "average_sentiment": random.randint(70, 95),
        "top_keyword": random.choice(["Performance", "Dark Mode", "Sync", "Battery"]),
        "urgent_count": random.randint(1, 5)
    }

if __name__ == "__main__":
    import uvicorn
    # FIXED: Changed port to 8000 to match Frontend configuration
    uvicorn.run(app, host="0.0.0.0", port=8000)