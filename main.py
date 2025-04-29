from fastapi import FastAPI
from pydantic import BaseModel
from chatquery_engine import chatbot, cache
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow frontend (localhost:3000) to talk to backend (localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local dev. (In prod, set specific domain.)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define request schema
class ChatRequest(BaseModel):
    message: str

# Define response schema (optional but clean)
class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    user_input = request.message
    bot_reply = chatbot(user_input)

    return ChatResponse(response=bot_reply)
