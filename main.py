import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Thread, Post

app = FastAPI(title="Forum API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ThreadCreate(Thread):
    pass

class PostCreate(Post):
    pass

class ThreadOut(BaseModel):
    id: str
    title: str
    author: str
    content: str
    category: Optional[str] = None
    tags: Optional[List[str]] = None

class PostOut(BaseModel):
    id: str
    thread_id: str
    author: str
    content: str

@app.get("/")
def read_root():
    return {"message": "Forum API is running"}

@app.get("/schema")
def read_schema():
    # Expose schemas for the Flames DB viewer
    return {
        "thread": Thread.model_json_schema(),
        "post": Post.model_json_schema(),
    }

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response

# Utility to convert Mongo docs to output models

def to_thread_out(doc) -> ThreadOut:
    return ThreadOut(
        id=str(doc.get("_id")),
        title=doc.get("title"),
        author=doc.get("author"),
        content=doc.get("content"),
        category=doc.get("category"),
        tags=doc.get("tags"),
    )


def to_post_out(doc) -> PostOut:
    return PostOut(
        id=str(doc.get("_id")),
        thread_id=str(doc.get("thread_id")),
        author=doc.get("author"),
        content=doc.get("content"),
    )

# Forum endpoints

@app.post("/threads", response_model=dict)
def create_thread(payload: ThreadCreate):
    thread_id = create_document("thread", payload)
    return {"id": thread_id}


@app.get("/threads", response_model=List[ThreadOut])
def list_threads(limit: int = 50, q: Optional[str] = None, category: Optional[str] = None):
    filter_dict = {}
    if q:
        filter_dict["title"] = {"$regex": q, "$options": "i"}
    if category:
        filter_dict["category"] = category
    docs = get_documents("thread", filter_dict, limit)
    return [to_thread_out(doc) for doc in docs]


@app.get("/threads/{thread_id}", response_model=ThreadOut)
def get_thread(thread_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    doc = db["thread"].find_one({"_id": ObjectId(thread_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Thread not found")
    return to_thread_out(doc)


@app.post("/threads/{thread_id}/posts", response_model=dict)
def create_post(thread_id: str, payload: PostCreate):
    # Ensure thread exists
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    thread = db["thread"].find_one({"_id": ObjectId(thread_id)})
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Force thread_id from path
    post_data = payload.model_dump()
    post_data["thread_id"] = thread_id
    post_id = create_document("post", post_data)
    return {"id": post_id}


@app.get("/threads/{thread_id}/posts", response_model=List[PostOut])
def list_posts(thread_id: str, limit: int = 100):
    docs = get_documents("post", {"thread_id": thread_id}, limit)
    return [to_post_out(doc) for doc in docs]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
