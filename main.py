# main.py
from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId
import os
import shutil

# -----------------------------
# BASIC SETUP
# -----------------------------
app = FastAPI(title="FastAPI + MongoDB")

# STATIC FOLDER (RENDER SAFE)
STATIC_FOLDER = "static/images"
os.makedirs(STATIC_FOLDER, exist_ok=True)

# STATIC MOUNT
app.mount("/static", StaticFiles(directory="static"), name="static")

load_dotenv()

# -----------------------------
# MONGODB CONNECTION
# -----------------------------
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

# -----------------------------
# HELPER
# -----------------------------
def obj_to_dict(doc):
    doc["id"] = str(doc["_id"])
    doc.pop("_id")
    return doc


# -----------------------------
# CREATE ITEM (FORM-DATA + IMAGE UPLOAD)
# -----------------------------
@app.post("/items")
async def create_item(
    name: str = Form(...),
    age: int = Form(...),
    city: str = Form(...),
    image: UploadFile | None = File(None)
):

    image_url = None

    if image:
        # File save path
        file_location = f"{STATIC_FOLDER}/{image.filename}"

        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        # Render URL (IMPORTANT)
        render_url = os.getenv(
            "RENDER_URL",
            "https://fastapi-mongodb-app.onrender.com"
        )

        image_url = f"{render_url}/static/images/{image.filename}"

    # Create DB document
    item = {
        "name": name,
        "age": age,
        "city": city,
        "image": image_url
    }

    result = col.insert_one(item)
    saved = col.find_one({"_id": result.inserted_id})

    return obj_to_dict(saved)


# -----------------------------
# TEST ROUTE
# -----------------------------
@app.get("/")
async def home():
    return {"message": "FastAPI Render Working!"}
