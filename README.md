# poc_chatbot

## Overview
A proof-of-concept chatbot application using PostgreSQL (with pgvector), Anthropic API, and FastAPI.

## Features
- Stores documents and embeddings in PostgreSQL with pgvector
- Uses Anthropic API for LLM responses
- Chunking and retrieval for document search
- FastAPI backend with static file serving

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