from app import models, database, main
from app.main import get_password_hash, verify_password, create_access_token

def test_auth_flow():
    db = database.SessionLocal()
    try:
        print("1. Testing DB Connection...")
        # Check if we can query
        count = db.query(models.User).count()
        print(f"   Current user count: {count}")

        print("2. Creating Test User...")
        username = "debug_user"
        password = "debug_password"
        email = "debug@example.com"
        
        # Cleanup potential previous run
        existing = db.query(models.User).filter(models.User.username == username).first()
        if existing:
            db.delete(existing)
            db.commit()
            print("   Deleted old debug user.")

        hashed = get_password_hash(password)
        print(f"   Hash generated: {hashed[:20]}...")
        
        new_user = models.User(
            username=username,
            email=email,
            hashed_password=hashed, # Ensure this matches the model field name
            full_name="Debug User"
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        print(f"   User created with ID: {new_user.id}")

        print("3. Verifying Password...")
        fetched_user = db.query(models.User).filter(models.User.username == username).first()
        if not fetched_user:
            print("   ERROR: User not found after commit!")
            return

        is_valid = verify_password(password, fetched_user.hashed_password)
        print(f"   Password valid? {is_valid}")
        
        if not is_valid:
            print(f"   Stored hash: {fetched_user.hashed_password}")
            
        print("4. Generating Token...")
        token = create_access_token(data={"sub": fetched_user.username})
        print(f"   Token generated: {token[:20]}...")

        print("SUCCESS: Auth parts work correctly.")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_auth_flow()
