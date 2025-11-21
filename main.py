from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import shutil
import os

app = FastAPI(title="FastAPI + MongoDB")

# Static Files
STATIC_DIR = "static/images"
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

load_dotenv()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

SECRET_KEY = "mysecret"
ALGORITHM = "HS256"

# ---------------- JWT ----------------
def create_access_token(data: dict, expires_delta=None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=60))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def hash_password(password: str):
    return pwd_context.hash(password[:72])

def verify_password(password: str, hashed):
    return pwd_context.verify(password, hashed)

# ---------------- MongoDB ----------------
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
user_col = db["users"]

# ---------------- Helpers ----------------
def obj_to_dict(doc):
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


# ---------------- Pydantic Models ----------------
class UserRegister(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str


# ---------------- USER AUTH ----------------
@app.post("/register")
def register(user: UserRegister):
    if user_col.find_one({"username": user.username}):
        raise HTTPException(400, "Username already exists")

    user_col.insert_one({
        "username": user.username,
        "password": hash_password(user.password)
    })

    return {"message": "User registered successfully"}


@app.post("/login")
def login(data: UserLogin):
    user = user_col.find_one({"username": data.username})
    if not user:
        raise HTTPException(400, "Invalid username or password")

    if not verify_password(data.password, user["password"]):
        raise HTTPException(400, "Invalid username or password")

    token = create_access_token({"id": str(user["_id"])})
    return {"access_token": token, "token_type": "bearer"}


# ---------------- Protected User ----------------
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("id")

        user = user_col.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(401, "User not found")

        return user

    except:
        raise HTTPException(401, "Token invalid or expired")


# ---------------- ITEMS CRUD ----------------
@app.get("/items")
def get_all_items(current_user=Depends(get_current_user)):
    items = [obj_to_dict(doc) for doc in col.find()]
    return items


@app.post("/items")
async def create_item(
    name: str = Form(...),
    age: int = Form(...),
    city: str = Form(...),
    image: UploadFile = File(None),
    current_user=Depends(get_current_user)
):
    image_url = None

    if image:
        filename = image.filename.replace(" ", "_")
        file_path = f"static/images/{filename}"

        with open(file_path, "wb") as f:
            f.write(await image.read())

        image_url = f"https://fastapi-mongodb-app.onrender.com/static/images/{filename}"

    item = {
        "name": name,
        "age": age,
        "city": city,
        "image": image_url
    }

    res = col.insert_one(item)
    saved = col.find_one({"_id": res.inserted_id})

    return obj_to_dict(saved)


@app.get("/items/{item_id}")
def get_item(item_id: str, current_user=Depends(get_current_user)):
    doc = col.find_one({"_id": ObjectId(item_id)})
    if not doc:
        raise HTTPException(404, "Item not found")
    return obj_to_dict(doc)


@app.patch("/items/{item_id}")
async def update_item(
    item_id: str,
    name: str = Form(None),
    age: int = Form(None),
    city: str = Form(None),
    image: UploadFile = File(None),
    current_user=Depends(get_current_user)
):
    update_data = {}

    if name:
        update_data["name"] = name
    if age is not None:
        update_data["age"] = age
    if city:
        update_data["city"] = city

    if image:
        filename = image.filename.replace(" ", "_")
        path = f"static/images/{filename}"

        with open(path, "wb") as f:
            shutil.copyfileobj(image.file, f)

        update_data["image"] = f"https://fastapi-mongodb-app.onrender.com/static/images/{filename}"

    if not update_data:
        raise HTTPException(400, "No data to update")

    col.update_one({"_id": ObjectId(item_id)}, {"$set": update_data})
    updated = col.find_one({"_id": ObjectId(item_id)})
    return obj_to_dict(updated)


@app.delete("/items/{item_id}")
def delete_item(item_id: str, current_user=Depends(get_current_user)):
    doc = col.find_one_and_delete({"_id": ObjectId(item_id)})
    if not doc:
        raise HTTPException(404, "Item not found")

    return obj_to_dict(doc)
