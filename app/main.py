from fastapi import FastAPI, HTTPException, status, Depends
import uvicorn
from app.database.mongo import db
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from app.models.user import UserCreate, UserOut, UserLogin
from app.core.security import hash_password, verify_password
from app.core.jwt import create_access_token
from bson import ObjectId
import os
from app.core.auth import get_current_user

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"message": "pong"}

@app.get("/dbtest")
async def test_db():
    try:
        # List all collection names
        collections = await db.list_collection_names()
        return {
            "status": "connected",
            "collections": collections
        }
    except Exception as e:
        return {
            "status": "error",
            "details": str(e)
        }

@app.post("/register", response_model=UserOut)
async def register(user: UserCreate):
    # Check if email already exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    # Hash the password
    hashed_password = hash_password(user.password)
    # Create user document (set username = email for legacy compatibility)
    user_doc = {
        "username": user.email,  # for legacy/compat
        "email": user.email,
        "hashed_password": hashed_password
    }
    # Insert user into database
    result = await db.users.insert_one(user_doc)
    # Return user data (excluding password)
    return UserOut(
        id=str(result.inserted_id),
        email=user.email
    )

@app.post("/login")
async def login(user: UserLogin):
    # Look up user by email
    user_doc = await db.users.find_one({"email": user.email})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    # Verify password
    if not verify_password(user.password, user_doc["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    # Create JWT token with email as sub
    access_token = create_access_token({"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me")
async def me(current_user=Depends(get_current_user)):
    """
    Returns the current user's email address. Requires JWT authentication.
    """
    return {"email": current_user.get("sub")}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 