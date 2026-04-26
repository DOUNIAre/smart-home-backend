from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import random
import string

# Internal Imports
import models, schemas, security
from database import engine, get_db
from services import resolver, rules, weather
from ai.recommender import recommender
from fastapi.security import OAuth2PasswordRequestForm

# Initialize Database Tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Home AI System - Final Version")
@app.get("/")
def read_root():
    return {
        "message": "Smart Home API is Online",
        "status": "Running",
        "docs": "/docs"
    }

# --- HELPER FUNCTIONS ---

def save_weather_to_db(db: Session, house_id: int, temp: int, weather_desc: str):
    """Internal helper to save environment snapshots to the database."""
    new_env = models.Environment(
        house_id=house_id,
        temperature=int(temp),
        weather=weather_desc
    )
    db.add(new_env)
    db.commit()
    db.refresh(new_env)
    return new_env

# --- AUTHENTICATION ROUTES ---

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2 uses 'username' field for the email input in Swagger
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    if not user or not security.verify_password(form_data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid Email or Password")
    
    access_token = security.create_access_token(data={"user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me/", response_model=schemas.UserOut)
def get_my_profile(current_user: models.User = Depends(security.get_current_user)):
    return current_user

# --- USER & HOUSE MANAGEMENT ---

@app.post("/users/", response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = security.get_password_hash(user.password)
    new_user = models.User(name=user.name, email=user.email, password=hashed_pwd)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/houses/", response_model=schemas.HouseOut)
def create_house(house: schemas.HouseCreate, db: Session = Depends(get_db), current_user: models.User = Depends(security.get_current_user)):
    # Generate random 6-char invite code
    random_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    new_house = models.House(name=house.name, invite_code=random_code)
    db.add(new_house)
    db.commit()
    db.refresh(new_house)
    
    # Creator becomes the Owner in Membership table
    new_membership = models.Membership(user_id=current_user.id, house_id=new_house.id, role="owner")
    db.add(new_membership)
    db.commit()
    return new_house

@app.post("/houses/join/")
def join_house(join_data: schemas.HouseJoin, db: Session = Depends(get_db)):
    house = db.query(models.House).filter(models.House.invite_code == join_data.invite_code).first()
    if not house:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    
    existing = db.query(models.Membership).filter(models.Membership.user_id == join_data.user_id, models.Membership.house_id == house.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already a member")
    
    new_member = models.Membership(user_id=join_data.user_id, house_id=house.id, role="member")
    db.add(new_member)
    db.commit()
    return {"message": f"Successfully joined {house.name}"}

# --- ROOMS & DEVICES ---

@app.post("/houses/{house_id}/rooms/", response_model=schemas.RoomOut)
def create_room(house_id: int, room: schemas.RoomCreate, db: Session = Depends(get_db)):
    new_room = models.Room(name=room.name, room_type=room.room_type, house_id=house_id)
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    return new_room

@app.post("/rooms/{room_id}/devices/", response_model=schemas.DeviceOut)
def add_device(room_id: int, device: schemas.DeviceCreate, db: Session = Depends(get_db)):
    # 1. Verify room exists
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # 2. Create device (OWNER_ID REMOVED FROM HERE)
    new_device = models.SmartDevice(
        name=device.name,
        device_type=device.device_type,
        room_id=room_id,
        status=False, 
        value=0       
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    return new_device

# --- CONTROL & LOGIC ---

@app.post("/devices/{device_id}/toggle")
def toggle_device(
    device_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(security.get_current_user)
):
    # 1. Find device
    device = db.query(models.SmartDevice).filter(models.SmartDevice.id == device_id).first()
    if not device: 
        raise HTTPException(status_code=404, detail="Device not found")

    # 2. NEW AUTHORITY CHECK: Check RoomAssignment
    # Does THIS user have a row in RoomAssignment for THIS room?
    assignment = db.query(models.RoomAssignment).filter(
        models.RoomAssignment.user_id == current_user.id,
        models.RoomAssignment.room_id == device.room_id
    ).first()
    
    if not assignment:
        raise HTTPException(
            status_code=403, 
            detail="Access Denied: You are not assigned to this room."
        )

    # 3. CONFLICT DETECTION: Count users assigned to this room
    user_count = db.query(models.RoomAssignment).filter(
        models.RoomAssignment.room_id == device.room_id
    ).count()

    # If more than 1 person lives in this room, use the Preference Resolver
    if user_count > 1:
        return {
            "status": "conflict_detected",
            "message": f"There are {user_count} users in this room. Use 'Apply Logic' to resolve."
        }

    # 4. SAFETY RULES (Priority check)
    is_safe, msg = rules.check_all_rules(db, device.room_id, device.device_type, not device.status)
    if not is_safe:
        raise HTTPException(status_code=400, detail=msg)

    # 5. EXECUTE & LOG
    device.status = not device.status
    
    history = models.DeviceActionHistory(
        device_id=device.id, user_id=current_user.id,
        action_type="TOGGLE", new_value=1 if device.status else 0, origin="MANUAL"
    )
    db.add(history)
    db.commit()
    
    return {"status": "success", "new_status": device.status}

@app.get("/rooms/{room_id}/apply-logic/{category}")
def apply_conflict_resolution(room_id: int, category: str, db: Session = Depends(get_db)):
    final_value = resolver.resolve_conflicts(db, room_id, category)
    if final_value is None: return {"message": "No preferences"}

    devices = db.query(models.SmartDevice).filter(models.SmartDevice.room_id == room_id, models.SmartDevice.device_type == category).all()
    for d in devices:
        if d.owner_id is None: # Only shared devices
            d.value = int(final_value)
            if category in ["LIGHT", "AC"]: d.status = True if final_value > 0 else False
    db.commit()
    return {"resolved_value": final_value}

# --- AI & ENVIRONMENT ---

@app.get("/houses/{house_id}/recommendation/", response_model=schemas.RecommendationOut)
def get_ai_recommendation(house_id: int, db: Session = Depends(get_db)):
    # 1. Fetch live weather
    online_data = weather.fetch_online_weather()
    if not online_data["success"]:
        # Fallback if key 401: Simulate for development
        temp, desc = 25, "Clear"
    else:
        temp, desc = online_data["temp"], online_data["weather"]

    # 2. Save context to DB
    save_weather_to_db(db, house_id, temp, desc)

    # 3. Call AI Module
    prefs = db.query(models.UserPreference).all()
    return recommender.generate_recommendation(prefs, {"outdoor_temp": temp, "condition": desc}, [])

@app.post("/feedback/")
def submit_feedback(fb: schemas.FeedbackCreate, db: Session = Depends(get_db)):
    # Record Feedback
    new_fb = models.UserFeedback(recommendation_id=fb.recommendation_id, user_id=fb.user_id, response=fb.response)
    db.add(new_fb)
    
    # Notify User
    msg = "Recommendation Accepted" if fb.response else "Recommendation Declined"
    notif = models.Notification(user_id=fb.user_id, message=msg)
    db.add(notif)
    
    db.commit()
    return {"message": "Feedback saved"}

# --- SUMMARY & HISTORY ---

@app.get("/houses/{house_id}/summary", response_model=schemas.HouseSummary)
def get_house_summary(house_id: int, db: Session = Depends(get_db)):
    house = db.query(models.House).filter(models.House.id == house_id).first()
    if not house: raise HTTPException(status_code=404, detail="House not found")

    room_summaries = []
    total_savings = 0.0
    rooms = db.query(models.Room).filter(models.Room.house_id == house_id).all()
    
    for r in rooms:
        active_count = db.query(models.SmartDevice).filter(models.SmartDevice.room_id == r.id, models.SmartDevice.status == True).count()
        
        # Energy logic: 0.5kWh per accepted feedback in this room (needs to be discussed)
        saved = db.query(models.UserFeedback).join(models.Recommendation).filter(
            models.Recommendation.device_id.in_(db.query(models.SmartDevice.id).filter(models.SmartDevice.room_id == r.id)),
            models.UserFeedback.response == True
        ).count() * 0.5
        
        total_savings += saved
        room_summaries.append(schemas.RoomSummary(id=r.id, name=r.name, active_devices_count=active_count, energy_saved_kwh=saved))

    return schemas.HouseSummary(house_id=house.id, house_name=house.name, total_energy_saved=total_savings, rooms=room_summaries)

@app.get("/houses/{house_id}/history", response_model=List[schemas.HistoryOut])
def get_house_history(house_id: int, db: Session = Depends(get_db)):
    return db.query(models.DeviceActionHistory).join(models.SmartDevice).join(models.Room).filter(
        models.Room.house_id == house_id
    ).order_by(models.DeviceActionHistory.timestamp.desc()).all()

# --- ROOM ASSIGNMENT ROUTE ---
# This is the "Key" that allows a user to control devices in a specific room.

@app.post("/rooms/{room_id}/assign/{user_id}")
def assign_user_to_room(room_id: int, user_id: int, db: Session = Depends(get_db)):
    # 1. Check if the user exists
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Check if the room exists
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # 3. Check if they are already assigned (Avoid duplicates)
    existing = db.query(models.RoomAssignment).filter(
        models.RoomAssignment.room_id == room_id,
        models.RoomAssignment.user_id == user_id
    ).first()
    
    if existing:
        return {"message": "User is already assigned to this room"}

    # 4. Create the link in the Database
    new_assignment = models.RoomAssignment(room_id=room_id, user_id=user_id)
    db.add(new_assignment)
    db.commit()
    
    return {"message": f"User {user.name} successfully assigned to {room.name}"}