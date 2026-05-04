# ContactBot — AI-Powered Contact Form Chatbot

A conversational contact form chatbot built with LangGraph and Flask. Instead of a traditional static form, users chat with an AI bot that collects their name, email, phone number, and message through natural conversation — validating each field in real time.

---

## Demo

```
Bot: Hi there! Welcome! I'm here to help connect you with our team.
     Could you please share your full name?

User: John

Bot: Thanks John! Could you share your email address?

User: john@gmail.com

Bot: Got it! Now could you share your 10-digit phone number?

User: 9876543210

Bot: Almost done! What message would you like to send to our team?

User: I need help with my order

Bot: Thank you John! We've received your message and our team
     will get back to you soon!
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Groq API — `meta-llama/llama-4-scout-17b-16e-instruct` |
| Agent Framework | LangGraph |
| LLM Tooling | LangChain + LangChain Groq |
| Validation | LangChain `@tool` decorator |
| Structured Output | Pydantic BaseModel |
| Backend | Flask |
| Database | SQLite |
| Checkpointing | LangGraph SqliteSaver |
| Logging | Python built-in `logging` module |
| Frontend | Plain HTML + CSS + JavaScript |

---

## Project Structure

```
contact-us-assignment/
├── app.py              ← Flask server — entry point, run this file
├── graph.py            ← LangGraph graph assembly
├── state.py            ← ContactState TypedDict + Pydantic classes
├── nodes.py            ← All 8 LangGraph node functions
├── tools.py            ← 3 validation @tool functions
├── database.py         ← All SQLite functions
├── logger.py           ← Python logging setup
├── .env                ← API keys (never commit this)
├── contact.db          ← auto-created on first run
├── checkpoints.db      ← auto-created on first run (LangGraph checkpoints)
├── contact_logs.log    ← auto-created on first run
├── templates/
│   ├── index.html      ← Landing page with chat widget
│   └── logs.html       ← Admin logs page
└── static/
    ├── style.css        ← All styling
    └── script.js        ← All JavaScript
```

---

## Architecture

This project uses a **monolithic architecture** — Flask and LangGraph run in the same Python process. After every `invoke()` call, Flask saves all data directly to SQLite using database functions. No internal HTTP APIs needed.

```
Browser
   │
   ├── POST /chat/start ──▶ Save session → Run graph → Save greeting
   │
   ├── POST /chat ────────▶ Save user msg → Resume graph → Save bot reply
   │                                                      → Save error (if crash)
   │                                                      → Save contact (if done)
   │
   ├── GET  /logs ────────▶ Paginated sessions list
   ├── GET  /logs/<id>/conversation ──▶ Full chat history
   ├── GET  /logs/<id>/errors ────────▶ System errors
   └── GET  /logs/<id>/details ───────▶ Submitted contact data
```

### LangGraph Flow

```
START
  ↓
askName → validateName ──invalid──▶ askName (retry)
                       ──valid───▶
                                   askEmail → validateEmail ──invalid──▶ askEmail (retry)
                                                            ──valid───▶
                                                                        askPhone → validatePhone ──invalid──▶ askPhone (retry)
                                                                                                ──valid───▶
                                                                                                            askMessage → saveToDB → END
```

### Database Tables

| Table | Purpose |
|-------|---------|
| `sessions` | Every chat session — status Incomplete/Completed |
| `chats` | Every message — bot and user |
| `contacts` | Final submitted form data |
| `errors` | System crashes from LangGraph nodes |

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd contact-us-assignment
```

### 2. Create virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install langgraph langchain langchain-groq langchain-core pydantic flask langgraph-checkpoint-sqlite python-dotenv
```

### 4. Get Groq API Key

1. Go to [https://console.groq.com](https://console.groq.com)
2. Sign up and create an API key
3. Copy the key

### 5. Create .env file

```
GROQ_API_KEY=your_api_key_here
```

### 6. Run the app

```bash
python app.py
```

Open your browser and go to:
```
http://127.0.0.1:5000
```

---

## Pages

### Landing Page — `http://127.0.0.1:5000`
Company home page with a floating chat button. Click the chat icon to open the bot and start the conversation.

### Admin Logs — `http://127.0.0.1:5000/logs-page`
Paginated table of all sessions. Click **View** on any session to open a popup with 3 tabs:
- **Conversation** — full chat history
- **Errors** — any system crashes during that session
- **Details** — final submitted contact data

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat/start` | Start a new session, get greeting |
| `POST` | `/chat` | Send a message, get bot reply |
| `GET` | `/logs` | Paginated sessions list |
| `GET` | `/logs/<session_id>/conversation` | Full chat history |
| `GET` | `/logs/<session_id>/errors` | System errors |
| `GET` | `/logs/<session_id>/details` | Submitted contact details |

---

## Validation Rules

| Field | Rules |
|-------|-------|
| Name | Letters and spaces only, minimum 2 characters, no numbers |
| Email | Must have `@`, valid domain, dot after `@` |
| Phone | Exactly 10 digits, numbers only |
| Message | Any text accepted |

---

## Key Design Decisions

**Why LangGraph?**
Multi-turn conversation with state persistence between messages. `interrupt_before` pauses the graph waiting for user input. `SqliteSaver` stores checkpoints so conversations survive server restarts.

**Why Groq?**
Fast inference, free tier available, no local model setup needed.

**Why monolithic architecture?**
Flask and LangGraph run together in one process. Simpler codebase, fewer files, direct database access. Suitable for learning and small-to-medium production deployments.

**Why SqliteSaver over MemorySaver?**
`MemorySaver` loses all conversation state on server restart. `SqliteSaver` persists checkpoints to `checkpoints.db` on disk — conversations survive restarts without needing PostgreSQL.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ Yes | Your Groq API key from console.groq.com |

---

## .gitignore

Make sure these are in your `.gitignore`:

```
.env
contact.db
checkpoints.db
contact_logs.log
venv/
__pycache__/
*.pyc
```

---

## License

This project is for educational purposes.