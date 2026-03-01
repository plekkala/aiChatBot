# poc_chatbot

## Overview
A proof-of-concept internal-document chatbot built with **FastAPI**, **PostgreSQL + pgvector**, and **Anthropic Claude**.  
Users upload documents (PDF, DOCX, PPTX, TXT, MD), the system converts them into vector embeddings stored in PostgreSQL, and employees can then ask natural-language questions that are answered by Claude using only the relevant excerpts retrieved from those documents (Retrieval-Augmented Generation, or **RAG**).

## Features
- Stores documents and vector embeddings in PostgreSQL with the pgvector extension
- Uses Anthropic Claude as the Large Language Model (LLM) for answer generation
- Automatic text chunking and semantic retrieval for accurate document search
- Multi-turn conversation support (conversation history passed to the LLM)
- FastAPI backend with a built-in Jinja2/HTML front-end (no separate JS framework needed)

---

## Architecture & Code Explanation

### Project layout

```
app/
├── main.py              # FastAPI application entry point
├── core/
│   └── config.py        # Settings loaded from .env (API keys, DB credentials, tuning params)
├── api/
│   ├── chat.py          # POST /api/chat and GET /api/chat/{id} routes
│   └── documents.py     # POST/GET/DELETE /api/documents routes
├── db/
│   └── models.py        # SQLAlchemy ORM models + DB session helpers
├── services/
│   ├── ingestion.py     # Document parsing → chunking → embedding → DB storage
│   ├── retrieval.py     # Semantic similarity search using pgvector
│   └── llm.py           # Claude prompt construction and API call
└── ui/
    └── templates/
        └── index.html   # Single-page chat UI (HTML + vanilla JS)
scripts/
└── init_db.py           # One-time script to initialise the database tables
tests/
└── test_ingestion.py    # Unit tests for the ingestion pipeline
```

---

### Key components explained

#### `app/core/config.py` — Configuration
Reads all configuration from the `.env` file using **pydantic-settings**.  
Important settings:

| Setting | Default | Purpose |
|---|---|---|
| `anthropic_api_key` | *(required)* | Key used to call Claude |
| `postgres_*` | localhost:5433 | PostgreSQL connection details |
| `chunk_size` | 512 | Max characters per document chunk |
| `chunk_overlap` | 50 | Overlap between consecutive chunks |
| `top_k_results` | 5 | Number of chunks retrieved per query |
| `claude_model` | claude-sonnet-4-6 | Claude model name |
| `max_tokens` | 1024 | Max tokens in Claude's reply |

---

#### `app/db/models.py` — Database models
Four SQLAlchemy tables are created on startup:

| Table | Description |
|---|---|
| `documents` | One row per uploaded file (filename, type, title) |
| `document_chunks` | One row per text chunk; stores the raw `content` and a 384-dimension `embedding` vector |
| `conversations` | One row per chat session (title derived from first user message) |
| `messages` | Each user and assistant turn stored with its role and timestamp |

`init_db()` runs `CREATE EXTENSION IF NOT EXISTS vector` to enable pgvector, then creates all tables.

---

#### `app/services/ingestion.py` — Document ingestion pipeline

When a file is uploaded the following steps run in order:

1. **Text extraction** — A format-specific reader pulls raw text out of the file:
   - `.pdf` → `pypdf.PdfReader`, one `(page_number, text)` tuple per page
   - `.docx` → `python-docx`, all paragraphs joined as a single block
   - `.pptx` → `python-pptx`, one block per slide
   - `.txt` / `.md` → decoded as UTF-8 (Markdown is HTML-converted then stripped)

2. **Chunking** — `langchain_text_splitters.RecursiveCharacterTextSplitter` splits each page/block into chunks of up to `chunk_size` characters, with `chunk_overlap` characters of shared context between adjacent chunks.

3. **Embedding** — `sentence-transformers` (`all-MiniLM-L6-v2`, 384 dimensions) converts every chunk into a normalised float vector in one batched call.

4. **Persistence** — A `Document` record is inserted first (to get an ID), then all `DocumentChunk` rows (chunk text + embedding vector + page number) are bulk-inserted.

---

#### `app/services/retrieval.py` — Semantic search

Given a user query string:

1. The same `all-MiniLM-L6-v2` model embeds the query into a 384-dimension vector (`embed_query()`).
2. A raw SQL query uses pgvector's `<=>` cosine-distance operator to rank every stored chunk by similarity to the query vector, returning the `top_k` closest chunks.
3. Similarity is reported as `1 − cosine_distance` (range 0–1; higher is more similar).

---

#### `app/services/llm.py` — Answer generation with Claude

1. **Context block** — The retrieved chunks are formatted as labelled excerpts with source title, page number, and relevance percentage.
2. **Message list** — Previous conversation messages (from DB) are prepended so Claude is aware of the dialogue history (multi-turn support).
3. **System prompt** — Claude is instructed to answer *only* from the provided context, cite sources inline, and refuse to guess when information is absent.
4. **API call** — `anthropic.Anthropic.messages.create()` is called with the assembled messages.
5. **Citations** — Unique `(document_id, page_number)` pairs from the retrieved chunks are deduplicated and returned alongside the answer text and token usage counts.

---

#### `app/api/chat.py` — Chat API routes

| Route | Method | Description |
|---|---|---|
| `/api/chat` | POST | Accept a user message, run the full RAG pipeline, return answer + citations |
| `/api/chat/{id}` | GET | Return the full message history for a conversation |

#### `app/api/documents.py` — Documents API routes

| Route | Method | Description |
|---|---|---|
| `/api/documents` | POST | Upload a file (≤ 50 MB), run ingestion, return chunk count |
| `/api/documents` | GET | List all indexed documents |
| `/api/documents/{id}` | DELETE | Remove a document and all its chunks (cascade) |

---

## What Happens When a Search (Chat Query) Is Submitted from the Front End

The following is the complete end-to-end flow when a user types a question and presses **Enter** or the **Send** button.

### Step 1 — User submits the query (browser)
The `sendMessage()` function in `index.html` fires:
- The textarea value is read and trimmed.
- The input field is cleared and the Send button is disabled to prevent double-submission.
- The user's message is immediately rendered in the chat window (`appendMessage("user", text)`).
- An animated three-dot loading indicator is added to signal that a response is in progress (`appendLoading()`).

### Step 2 — HTTP POST to `/api/chat` (browser → server)
```
POST /api/chat
Content-Type: application/json

{ "message": "<user question>", "conversation_id": "<UUID or null>" }
```
On the very first message `conversation_id` is `null`; for follow-up messages the ID returned by the previous response is re-sent so the server can load existing history.

### Step 3 — Load or create conversation (server, `chat.py`)
- If `conversation_id` is provided, the `Conversation` row is fetched from PostgreSQL. A 404 is raised if it does not exist.
- If no `conversation_id` is provided, a new `Conversation` row is created (title set to the first 60 characters of the user message).

### Step 4 — Semantic retrieval (server, `retrieval.py`)
`retrieve_relevant_chunks(db, message)` is called:

1. The user's message is encoded into a 384-dimension embedding vector by `all-MiniLM-L6-v2`.
2. PostgreSQL is queried:
   ```sql
   SELECT ... , 1 - (dc.embedding <=> CAST(:query_vec AS vector)) AS similarity
   FROM document_chunks dc
   JOIN documents d ON d.id = dc.document_id
   ORDER BY dc.embedding <=> CAST(:query_vec AS vector)
   LIMIT :top_k
   ```
   pgvector's `<=>` operator computes cosine distance between the stored chunk embeddings and the query embedding. The rows are sorted by ascending distance (most similar first) and the top `top_k` (default 5) are returned.
3. Each result contains the chunk text, source document name, page number, and similarity score.

### Step 5 — Build conversation history (server, `chat.py`)
All previously stored `Message` rows for this conversation are loaded from the database and formatted as `{"role": "user"|"assistant", "content": "..."}` dictionaries. This list is passed to the LLM so it can maintain context across multiple turns.

### Step 6 — Generate answer with Claude (server, `llm.py`)
`generate_answer(message, chunks, conversation_history)` is called:

1. The retrieved chunks are formatted into a context block:
   ```
   [Excerpt 1]
   Source: <document title>  |  Page: <n>  |  Relevance: 87%
   <chunk text>

   ---

   [Excerpt 2]
   ...
   ```
2. The final user message is wrapped with `<context>` and `<question>` XML tags.
3. All prior conversation turns are prepended to the message list, then the current user message is appended.
4. Claude is called via `anthropic.Anthropic.messages.create()` with a strict system prompt that instructs it to:
   - Answer *only* from the provided context excerpts.
   - Cite the source document and page inline.
   - Clearly state when the context is insufficient rather than guessing.
5. The response text is extracted and unique citation objects are assembled (deduplicating by document + page).

### Step 7 — Persist messages (server, `chat.py`)
Both the user message and the assistant answer are saved as `Message` rows linked to the conversation, so they are available as history for future turns.

### Step 8 — Return response (server → browser)
```json
{
  "answer": "...",
  "conversation_id": "<UUID>",
  "citations": [
    {
      "document_title": "Employee Handbook",
      "filename": "employee_handbook.pdf",
      "page_number": 12,
      "similarity": 0.87
    }
  ],
  "input_tokens": 542,
  "output_tokens": 118
}
```

### Step 9 — Render the answer (browser)
Back in `sendMessage()`:
- The loading indicator is removed.
- `conversationId` is updated with the returned UUID so the next message continues the same conversation.
- `appendMessage("assistant", data.answer, data.citations)` renders the answer bubble.
- If citations are present, a **Sources** panel is shown beneath the answer with the document title, page number, and similarity percentage.
- The Send button is re-enabled and focus returns to the textarea.

### Visual summary of the search flow

```
Browser                           FastAPI Server                  PostgreSQL / Claude
  │                                      │                               │
  │── POST /api/chat ──────────────────►│                               │
  │   { message, conversation_id }       │                               │
  │                                      │── Load/create Conversation ──►│
  │                                      │◄─ Conversation row ───────────│
  │                                      │                               │
  │                                      │── Embed query (MiniLM) ───────┤
  │                                      │── SELECT chunks ORDER BY      │
  │                                      │   cosine distance LIMIT 5 ──►│
  │                                      │◄─ Top-5 relevant chunks ──────│
  │                                      │                               │
  │                                      │── Build prompt + history      │
  │                                      │── Call Claude API ────────────►(Anthropic)
  │                                      │◄─ Answer text ─────────────────(Anthropic)
  │                                      │                               │
  │                                      │── INSERT user + assistant ────►│
  │                                      │   messages                    │
  │                                      │                               │
  │◄── { answer, citations, … } ────────│                               │
  │                                      │                               │
  │  Render answer bubble +              │                               │
  │  Sources panel in UI                 │                               │
```

---

## Setup

### Prerequisites
- Python 3.9+
- Docker & Docker Compose
- (Optional) VS Code

### Installation

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd poc_chatbot
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   - Edit `.env` with your Anthropic API key and desired DB credentials.

4. **Start PostgreSQL with Docker Compose**
   ```bash
   docker-compose up -d
   ```

5. **Initialize the database**
   ```bash
   set -o allexport; source .env; set +o allexport
   python scripts/init_db.py
   ```

6. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

### Troubleshooting

- **Postgres connection errors:**  
  Ensure `.env` matches Docker Compose port mapping (`POSTGRES_PORT=5433` if using `"5433:5432"`).
- **Role "postgres" does not exist:**  
  Recreate the DB volume:
  ```bash
  docker-compose down -v
  docker-compose up -d
  ```
- **Anthropic API credit error:**  
  Upgrade your Anthropic account or add credits.

- **Static directory error:**  
  Create missing directory:
  ```bash
  mkdir -p app/ui/static
  ```

## Development

- All Python code is in `app/`
- Database models: `app/db/models.py`
- Configuration: `app/core/config.py`
- Static files: `app/ui/static/`

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- Inspired by the need for efficient document retrieval and interaction.
- Leveraging modern AI and database technologies for a seamless experience.