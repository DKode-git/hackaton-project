import json
import os
import uuid
import time
import random
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Nexus Backend")

# --- 1. CONFIGURATION ---
FEEDBACK_FILE = "feedback.json"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. MODELS ---

class LoginRequest(BaseModel):
    username: str
    password: str

class FeedbackSubmission(BaseModel):
    text: str
    category: str
    username: str
    # Added this field so the frontend can send the admin status if needed
    admin: Optional[str] = "false" 
    priority: Optional[str] = "normal"

class FeedbackUpdate(BaseModel):
    status: str

class PolishRequest(BaseModel):
    text: str

# --- 3. DATABASE UTILS ---

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

# --- 4. AUTH ENDPOINTS ---

@app.post("/login")
def login(creds: LoginRequest):
    # --- LOGIC FIX START ---
    # List of users who should have Admin Access
    ADMIN_USERS = ["admin", "Fardeen", "Boss"] 
    
    if creds.username in ADMIN_USERS and creds.password == "password":
        return {
            "token": "admin-token",
            "username": creds.username,
            "role": "admin",   # Critical for routing
            "admin": "true"    # Critical for your specific check
        }
    # --- LOGIC FIX END ---
    
    return {
        "token": f"user-token-{uuid.uuid4()}",
        "username": creds.username,
        "role": "user",
        "admin": "false"
    }

# --- 5. CORE LOGIC ENDPOINTS ---

@app.get("/suggestions")
def get_suggestions(username: Optional[str] = None):
    data = load_json(FEEDBACK_FILE, [])
    
    if username:
        # User View: Filter by username
        user_data = [x for x in data if x.get("username") == username]
        return user_data
    
    # Admin View: Return everything
    return data

@app.post("/suggestions")
def create_suggestion(item: FeedbackSubmission):
    data = load_json(FEEDBACK_FILE, [])
    
    # AI Logic
    ai_sentiment = random.randint(40, 99)
    summary_text = " ".join(item.text.split()[:7]) + "..."
    if len(item.text) < 30: summary_text = item.text

    # LOGIC FIX: Determine if this post was made by an admin
    # We check the payload or default to the username check
    is_admin = "true" if item.username in ["admin", "Fardeen"] else "false"

    new_entry = {
        "id": str(uuid.uuid4().hex[:6]), 
        "status": "pending",
        "category": item.category,
        "text": item.text,
        "username": item.username,
        "admin": is_admin,  # <-- SAVING THE ADMIN TAG IN JSON
        "ai_summary": summary_text, 
        "ai_note": f"Sentiment detected: {ai_sentiment}% positive.",
        "sentiment": ai_sentiment,
        "date": datetime.now().strftime("%Y-%m-%d")
    }
    
    data.insert(0, new_entry) 
    save_json(FEEDBACK_FILE, data)
    return new_entry

@app.patch("/suggestions/{item_id}")
def update_suggestion(item_id: str, update: FeedbackUpdate):
    data = load_json(FEEDBACK_FILE, [])
    found = False
    
    for item in data:
        if item["id"] == item_id:
            item["status"] = update.status
            found = True
            break
            
    if found:
        save_json(FEEDBACK_FILE, data)
        return {"status": "success", "new_status": update.status}
    
    raise HTTPException(status_code=404, detail="Item not found")

@app.post("/ai/polish")
def ai_polish(payload: PolishRequest):
    time.sleep(0.5) 
    words = payload.text.split()
    if len(words) < 5:
        return {"polished": f"Standardized Request: {payload.text}"}
    return {"polished": f"✨ Optimized: {payload.text} (Enhanced for clarity)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)