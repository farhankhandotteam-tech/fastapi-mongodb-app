# main.py
from fastapi import FastAPI, HTTPException, Form, File, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import os
import shutil

# =========================
# BASIC SETUP
# =========================
app = FastAPI(title="FastAPI + MongoDB + Auth")

STATIC_DIR = "static/images"
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

load_dotenv()


# =========================
# MONGODB
# =========================
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://hotel:hotel@cluster0.qgjxf2y.mongodb.net/hoteldb"
)

client = MongoClient(
    MONGODB_URI,
    tls=True,
    tlsAllowInvalidCertificates=True
)

db = client["hoteldb"]
col = db["items"]
user_col = db["users"]  # NEW


# =========================
# HELPERS
# =========================
def obj_to_dict(doc):
    doc["id"] = str(doc["_id"])
    doc.pop("_id")
    return doc


# =========================
# SECURITY (JWT + Hash)
# =========================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = "MY_SUPER_SECRET_KEY_123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(password: str, hashed):
    return pwd_context.verify(password, hashed)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    """Verify user token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("id")
        if not user_id:
            raise HTTPException(401, "Invalid token")
    except:
        raise HTTPException(401, "Invalid or expired token")

    user = user_col.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(401, "User not found")

    user["id"] = str(user["_id"])
    user.pop("_id")
    return user


# =========================
# TEST ROUTES
# =========================
@app.get("/")
def home():
    return {"message": "API live — Authentication working!"}


@app.get("/hotel-db")
def hotel_test():
    d = col.find_one()
    return obj_to_dict(d) if d else {"status": "empty"}


# =========================
# AUTH ROUTES
# =========================
@app.post("/register")
def register(username: str = Form(...), password: str = Form(...)):
    if user_col.find_one({"username": username}):
        raise HTTPException(400, "Username already exists")

    user = {
        "username": username,
        "password": hash_password(password)
    }

    user_col.insert_one(user)
    return {"message": "User registered successfully"}


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    user = user_col.find_one({"username": username})
    if not user:
        raise HTTPException(400, "Invalid username or password")

    if not verify_password(password, user["password"]):
        raise HTTPException(400, "Invalid username or password")

    token = create_access_token({"id": str(user["_id"])})

    return {"access_token": token, "token_type": "bearer"}


# =========================
# CRUD ROUTES (PROTECTED)
# =========================

# CREATE ITEM
@app.post("/items")
async def create_item(
    current_user=Depends(get_current_user),
    name: str = Form(...),
    age: int = Form(...),
    city: str = Form(...),
    image: UploadFile = File(None)
):

    image_url = None

    # SAVE IMAGE
    if image:
        filename = image.filename.replace(" ", "_")
        path = f"static/images/{filename}"

        with open(path, "wb") as f:
            f.write(await image.read())

        image_url = f"https://fastapi-mongodb-app.onrender.com/static/images/{filename}"

    item = {
        "name": name,
        "age": age,
        "city": city,
        "image": image_url,
        "created_by": current_user["id"]
    }

    result = col.insert_one(item)
    saved = col.find_one({"_id": result.inserted_id})
    return obj_to_dict(saved)


# GET ONE
@app.get("/items/{item_id}")
def get_item(item_id: str, current_user=Depends(get_current_user)):
    doc = col.find_one({"_id": ObjectId(item_id)})
    if not doc:
        raise HTTPException(404, "Item not found")
    return obj_to_dict(doc)


# GET ALL
@app.get("/items")
def get_all_items(current_user=Depends(get_current_user)):
    items = [obj_to_dict(doc) for doc in col.find()]
    return items


# UPDATE ITEM
@app.patch("/items/{item_id}")
async def update_item(
    item_id: str,
    current_user=Depends(get_current_user),
    name: str = Form(None),
    age: int = Form(None),
    city: str = Form(None),
    image: UploadFile = File(None)
):
    update_data = {}

    if name:
        update_data["name"] = name
    if age is not None:
        update_data["age"] = age
    if city:
        update_data["city"] = city

    # IMAGE UPDATE
    if image:
        filename = image.filename.replace(" ", "_")
        filepath = f"static/images/{filename}"

        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        update_data["image"] = f"https://fastapi-mongodb-app.onrender.com/static/images/{filename}"

    if not update_data:
        raise HTTPException(400, "No data to update")

    result = col.update_one({"_id": ObjectId(item_id)}, {"$set": update_data})

    if result.matched_count == 0:
        raise HTTPException(404, "Item not found")

    updated_doc = col.find_one({"_id": ObjectId(item_id)})
    return obj_to_dict(updated_doc)


# DELETE ITEM
@app.delete("/items/{item_id}")
def delete_item(item_id: str, current_user=Depends(get_current_user)):
    doc = col.find_one_and_delete({"_id": ObjectId(item_id)})
    if not doc:
        raise HTTPException(404, "Item not found")
    return obj_to_dict(doc)
