# main.py
from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import os
import shutil

# -----------------------------
# BASIC SETUP
# -----------------------------
app = FastAPI(title="FastAPI + MongoDB")

# Static folder (Render safe)
STATIC_DIR = "static/images"
os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

load_dotenv()

# -----------------------------
# MONGODB
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
# HELPERS
# -----------------------------
def obj_to_dict(doc):
    doc["id"] = str(doc["_id"])
    doc.pop("_id")
    return doc


# -----------------------------
# TEST ROUTES
# -----------------------------
@app.get("/")
def home():
    return {"message": "API live — main.py working!"}


@app.get("/hotel-db")
def hotel_test():
    d = col.find_one()
    if d:
        return obj_to_dict(d)
    return {"status": "empty"}


# -----------------------------
# CREATE ITEM (WITH IMAGE)
# -----------------------------
@app.post("/items")
async def create_item(
    name: str = Form(...),
    age: int = Form(...),
    city: str = Form(...),
    image: UploadFile = File(None)
):

    image_url = None

    if image is not None:
        filename = image.filename.replace(" ", "_")
        file_path = f"static/images/{filename}"

        with open(file_path, "wb") as f:
            f.write(await image.read())  # BINARY ONLY

        # PUBLIC URL
        image_url = f"https://fastapi-mongodb-app.onrender.com/static/images/{filename}"

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
# GET ONE
# -----------------------------
@app.get("/items/{item_id}")
# READ ALL ITEMS
@app.get("/items")
def get_all_items():
    items = []
    for doc in col.find():
        items.append(obj_to_dict(doc))
    return items



# -----------------------------
# UPDATE ITEM
# -----------------------------
@app.patch("/items/{item_id}")
async def update_item(
    item_id: str,
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

    # image upload
    if image:
        save_path = "static/images"
        os.makedirs(save_path, exist_ok=True)

        filename = image.filename.replace(" ", "_")
        file_path = os.path.join(save_path, filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        update_data["image"] = f"https://fastapi-mongodb-app.onrender.com/static/images/{filename}"

    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")

    try:
        result = col.update_one({"_id": ObjectId(item_id)}, {"$set": update_data})
    except:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")

    updated_doc = col.find_one({"_id": ObjectId(item_id)})
    return obj_to_dict(updated_doc)
s


# -----------------------------
# DELETE ITEM
# -----------------------------
@app.delete("/items/{item_id}")
def delete_item(item_id: str):
    try:
        doc = col.find_one_and_delete({"_id": ObjectId(item_id)})
        if not doc:
            raise HTTPException(404, "Item not found")
        return obj_to_dict(doc)
    except:
        raise HTTPException(400, "Invalid ID")
