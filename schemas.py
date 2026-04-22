from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# --- USER SCHEMAS ---

# This is what the Android app SENDS when creating a user
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

# This is what the API sends BACK to the Android app
class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True # This allows Pydantic to read data from SQLAlchemy models

# --- HOUSE SCHEMAS ---

class HouseCreate(BaseModel):
    name: str

class HouseOut(BaseModel):
    id: int
    name: str
    invite_code: str

    class Config:
        from_attributes = True

class HouseJoin(BaseModel):
    user_id: int
    invite_code: str

# --- ROOM SCHEMAS ---
class RoomCreate(BaseModel):
    name: str
    room_type: str # e.g., "living_room", "bedroom" 

class RoomOut(BaseModel):
    id: int
    name: str
    house_id: int
    room_type: str

    class Config:
        from_attributes = True

# --- DEVICE SCHEMAS ---
class DeviceCreate(BaseModel):
    name: str
    device_type: str # e.g., "AC", "Light", "Heater"
    owner_id: Optional[int] = None # Optional! If empty, it's a shared device.

class DeviceOut(BaseModel):
    id: int
    name: str
    device_type: str
    status: bool
    value: int
    room_id: int
    owner_id: Optional[int]

    class Config:
        from_attributes = True

class PreferenceCreate(BaseModel):
    user_id: int
    category: str # e.g., "TEMPERATURE"
    value: int    # e.g., 22
    context: str  # e.g., "HOME"

class RecommendationOut(BaseModel):
    recommendation: str
    action: int
    confidence: float
    reason: str

class EnvironmentCreate(BaseModel):
    house_id: int
    temperature: int
    weather: str

class FeedbackCreate(BaseModel):
    recommendation_id: int
    user_id: int
    response: bool

class NotificationOut(BaseModel):
    id: int
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class HistoryOut(BaseModel):
    id: int
    device_id: int
    user_id: Optional[int]
    action_type: str
    new_value: int
    origin: str
    timestamp: datetime

    class Config:
        from_attributes = True


class EnvironmentOut(BaseModel):
    id: int
    house_id: int
    temperature: int
    weather: str
    timestamp: datetime

    class Config:
        from_attributes = True

class RoomSummary(BaseModel):
    id: int
    name: str
    active_devices_count: int # How many lights/AC are currently ON
    current_temp: Optional[int] = None
    energy_saved_kwh: float # Total energy saved in this room
    
class HouseSummary(BaseModel):
    house_id: int
    house_name: str
    total_energy_saved: float
    rooms: List[RoomSummary]