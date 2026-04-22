from sqlalchemy.orm import Session
import models

def check_safety_rules(db: Session, room_id: int, new_device_type: str, new_status: bool):
    """
    Returns True if the action is safe.
    Returns False if it violates a safety rule (like AC + Heater).
    """
    # Rule 1: If we are turning ON the AC, the Heater must be OFF.
    if new_device_type == "AC" and new_status == True:
        heater = db.query(models.SmartDevice).filter(
            models.SmartDevice.room_id == room_id,
            models.SmartDevice.device_type == "Heater",
            models.SmartDevice.status == True
        ).first()
        if heater:
            return False, "Cannot turn on AC while Heater is running!"

    # Rule 2: If we are turning ON the Heater, the AC must be OFF.
    if new_device_type == "Heater" and new_status == True:
        ac = db.query(models.SmartDevice).filter(
            models.SmartDevice.room_id == room_id,
            models.SmartDevice.device_type == "AC",
            models.SmartDevice.status == True
        ).first()
        if ac:
            return False, "Cannot turn on Heater while AC is running!"

    return True, "Safe"

# we can add more rules later for now thi