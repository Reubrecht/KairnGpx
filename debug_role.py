from app import models, database
from sqlalchemy.orm import Session
import enum

def debug_role():
    db = database.SessionLocal()
    try:
        # Find any super admin
        super_admin = db.query(models.User).filter(models.User.role == models.Role.SUPER_ADMIN).first()
        if not super_admin:
            # Try finding by string if enum match failed (though filter uses enum)
            print("No user found via Enum match. Checking all users...")
            users = db.query(models.User).all()
            for u in users:
                print(f"User: {u.username}, Role: {u.role}, Type: {type(u.role)}")
                if str(u.role) == "super_admin" or u.role == models.Role.SUPER_ADMIN:
                    super_admin = u
                    break
        
        if super_admin:
            print(f"Found Super Admin: {super_admin.username}")
            print(f"Role: {super_admin.role}")
            print(f"Type of role: {type(super_admin.role)}")
            
            try:
                print(f"Role value: {super_admin.role.value}")
            except AttributeError:
                print("ERROR: Role has no attribute 'value'!")
                
        else:
            print("No Super Admin found in DB.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    debug_role()
