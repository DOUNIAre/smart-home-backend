from sqlalchemy.orm import Session
import models

def resolve_conflicts(db: Session, room_id: int, device_type: str):
    """
    This function looks at everyone's preferences for a specific room
    and decides the final value for the devices.
    """
    
    # 1. Find all users belonging to the house this room is in
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    house_id = room.house_id
    
    # 2. Get all preferences for this house and category (e.g., TEMPERATURE)
    # In a real app, we'd filter by 'active' users or 'users currently at home'
    prefs = db.query(models.UserPreference).filter(
        models.UserPreference.category == device_type
    ).all()

    if not prefs:
        return None

    # 3. Logic based on Device Type
    if device_type == "TEMPERATURE" or device_type == "LIGHT_BRIGHTNESS":
        # CONTINUOUS STRATEGY: Weighted Average
        # (Owners get weight 2, Members weight 1)
        total_value = 0
        total_weight = 0
        
        for p in prefs:
            # Check user role in this house
            membership = db.query(models.Membership).filter(
                models.Membership.user_id == p.user_id,
                models.Membership.house_id == house_id
            ).first()
            
            weight = 2 if membership.role == "owner" else 1
            total_value += (p.value * weight)
            total_weight += weight
            
        return total_value / total_weight

    else:
        # BINARY STRATEGY: Majority Voting (for ON/OFF)
        on_votes = sum(1 for p in prefs if p.value > 0)
        off_votes = sum(1 for p in prefs if p.value == 0)
        
        return 1 if on_votes >= off_votes else 0