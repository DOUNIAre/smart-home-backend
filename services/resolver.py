from sqlalchemy.orm import Session
import models

def resolve_conflicts(db: Session, room_id: int, device_type: str):
    # 1. Get the list of User IDs assigned to THIS specific room
    assignments = db.query(models.RoomAssignment).filter(
        models.RoomAssignment.room_id == room_id
    ).all()
    
    assigned_user_ids = [a.user_id for a in assignments]

    if not assigned_user_ids:
        return None

    # 2. Get preferences ONLY for these specific users and this device type
    prefs = db.query(models.UserPreference).filter(
        models.UserPreference.user_id.in_(assigned_user_ids),
        models.UserPreference.category == device_type
    ).all()

    if not prefs:
        return None

    # 3. Choose the Strategy based on Device Type
    
    # STRATEGY A: Continuous Values (Temperature / Brightness)
    # We use a Weighted Average
    if device_type in ["TEMPERATURE", "AC", "BRIGHTNESS"]:
        room = db.query(models.Room).filter(models.Room.id == room_id).first()
        total_value = 0
        total_weight = 0
        
        for p in prefs:
            # Check if this user is the OWNER of the house
            membership = db.query(models.Membership).filter(
                models.Membership.user_id == p.user_id,
                models.Membership.house_id == room.house_id
            ).first()
            
            # Owner gets Weight 2, Member gets Weight 1
            weight = 2 if (membership and membership.role == "owner") else 1
            
            total_value += (p.value * weight)
            total_weight += weight
            
        return total_value / total_weight

    # STRATEGY B: Binary Decisions (Lights / ON-OFF switches)
    # We use Majority Voting
    else:
        on_votes = sum(1 for p in prefs if p.value > 0)
        off_votes = sum(1 for p in prefs if p.value == 0)
        
        # Returns 1 if ON wins or it's a tie, 0 if OFF wins
        return 1 if on_votes >= off_votes else 0