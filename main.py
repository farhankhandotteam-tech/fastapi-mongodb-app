# api.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from pymongo import MongoClient
from bson import ObjectId
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# -------- Load Environment Variables --------
load_dotenv()

# -------- MongoDB Connection (SSL FIX) --------
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://hotel:hotel@cluster0.qgjxf2y.mongodb.net/hoteldb?retryWrites=true&w=majority"
)

client = MongoClient(
    MONGODB_URI,
    tls=True,
    tlsAllowInvalidCertificates=True  # IMPORTANT SSL FIX
)

DB_NAME = os.getenv("DB_NAME", "hoteldb")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "items")

db = client[DB_NAME]
col = db[COLLECTION_NAME]

# -------- FastAPI Setup --------
app = FastAPI(title="FastAPI + MongoDB Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- Helper: Convert ObjectId --------
def obj_to_dict(doc):
    if not doc:
        return None
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return doc

# -------- Models --------
class ItemModel(BaseModel):
    name: str = Field(..., example="Alice")
    age: Optional[int] = Field(None, example=25)
    city: Optional[str] = Field(None, example="Delhi")

class UpdateItemModel(BaseModel):
    name: Optional[str]= None
    age: Optional[int]= None
    city: Optional[str]= None
    

# -------- Routes --------
@app.get("/hotel-db")
def hotel_db():
    data = collection.find_one()  # first document
    if data:
        return {"status": "connected", "data": data}
    else:
        return {"status": "connected but empty"}

@app.get("/")
def read_root():
    return {"message": "API is live "}


# CREATE
@app.post("/items")
def create_item(item: ItemModel):
    data = item.dict()
    result = col.insert_one(data)
    new_doc = col.find_one({"_id": result.inserted_id})
    return obj_to_dict(new_doc)


# READ ALL
@app.get("/items")
def list_items():
    docs = col.find()
    return [obj_to_dict(d) for d in docs]


# READ ONE
@app.get("/items/{item_id}")
def get_item(item_id: str):
    try:
        doc = col.find_one({"_id": ObjectId(item_id)})
    except:
        raise HTTPException(400, "Invalid ID format")

    if not doc:
        raise HTTPException(404, "Item not found")

    return obj_to_dict(doc)





# PARTIAL UPDATE (PATCH)
@app.patch("/items/{item_id}")
def update_item(item_id: str, item: UpdateItemModel):
    update_data = {k: v for k, v in item.dict().items() if v is not None}

    if not update_data:   # <-- Ye line
        raise HTTPException(400, "No data to update")

    try:
        res = col.update_one({"_id": ObjectId(item_id)}, {"$set": update_data})
    except:
        raise HTTPException(400, "Invalid ID format")
    
    if res.matched_count == 0:
        raise HTTPException(404, "Item not found")

    return obj_to_dict(col.find_one({"_id": ObjectId(item_id)}))



# DELETE
@app.delete("/items/{item_id}")
def delete_item(item_id: str):
    try:
        doc = col.find_one_and_delete({"_id": ObjectId(item_id)})
    except:
        raise HTTPException(400, "Invalid ID format")

    if not doc:
        raise HTTPException(404, "Item not found")

    return obj_to_dict(doc)
