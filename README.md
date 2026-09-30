# SEA Translation Chatbot with RAG

A multilingual chatbot powered by RAG (Retrieval-Augmented Generation) using MongoDB Atlas Vector Search and Sailor2 models for Southeast Asian languages.

## Features

- **6 SEA Languages Supported**: English, Chinese, Malay, Vietnamese, Thai, Tamil
- **RAG-Enhanced Responses**: MongoDB Atlas Vector Search with semantic retrieval
- **Real-time Streaming**: SSE-based streaming responses
- **PDF Knowledge Base**: Upload and process PDF documents
- **Conversation History**: Persistent storage in MongoDB
- **GridFS Storage**: Efficient PDF file management
- **Auto Language Detection**: Automatic source language detection

## Tech Stack

### Frontend
- **Next.js 16** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **React Markdown** - Markdown rendering

### Backend
- **FastAPI** - Python async web framework
- **Sailor2 Models** - SEA language translation (1B/8B)
- **Sentence Transformers** - Embeddings (768-dim)
- **MongoDB Atlas** - Vector Search & Storage
- **Motor** - Async MongoDB driver
- **PyPDF** - PDF processing

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│                  http://localhost:3000                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Backend (FastAPI)                           │
│                http://localhost:8000                         │
├─────────────────────────────────────────────────────────────┤
│  RAG Pipeline:                                               │
│  1. Language Detection                                       │
│  2. Translation to English (Sailor2)                         │
│  3. Query Summary Generation                                 │
│  4. MongoDB Atlas Vector Search (768-dim embeddings)         │
│  5. Context Translation to Target Language                   │
│  6. Streaming Response (SSE)                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           MongoDB Atlas (Vector Search)                      │
├─────────────────────────────────────────────────────────────┤
│  Database: VHACK                                             │
│  ├─ Collection: knowledge_base (RAG documents)              │
│  │  └─ Vector Search Index: default (768-dim)              │
│  │                                                            │
│  Database: sea_translate                                     │
│  ├─ Collection: messages (conversation history)             │
│  └─ GridFS: pdfs (PDF file storage)                         │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.10+
- **MongoDB Atlas** account with Vector Search enabled
- **HuggingFace Token** (for Sailor2 models)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd Hackathon
```

2. **Install frontend dependencies**
```bash
npm install
```

3. **Install backend dependencies**
```bash
cd src/app/api/translate
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cd src/app/api/translate
cp .env.example .env
# Edit .env with your configurations
```

### Environment Configuration

Edit `src/app/api/translate/.env`:

```env
# MongoDB Atlas Configuration
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>/?retryWrites=true&w=majority
MONGODB_DB=sea_translate
MONGODB_ATLAS_URI=mongodb+srv://<user>:<password>@<cluster>/?retryWrites=true&w=majority
MONGODB_ATLAS_DB=VHACK
MONGODB_ATLAS_COLLECTION=knowledge_base

# Field Mapping
MONGODB_TEXT_FIELD=text
MONGODB_SOURCE_FIELD=source
MONGODB_EMBEDDING_FIELD=embedding

# Vector Search Settings
MONGODB_USE_VECTOR_SEARCH=1
MONGODB_ATLAS_VECTOR_INDEX=default
MONGODB_RAG_TOP_K=3
MONGODB_RAG_NUM_CANDIDATES=60

# HuggingFace Token
HF_TOKEN=<your_huggingface_token>

# PDF Processing
PDF_DEFAULT_CHUNK_SIZE=1000
PDF_DEFAULT_CHUNK_OVERLAP=200
PDF_MAX_FILE_SIZE_MB=10
```

### MongoDB Atlas Setup

#### 1. Create Vector Search Index

In MongoDB Atlas, create a Vector Search index on `VHACK.knowledge_base`:

```json
{
  "mappings": {
    "dynamic": true,
    "fields": {
      "embedding": {
        "type": "knnVector",
        "dimensions": 768,
        "similarity": "cosine"
      },
      "text": {
        "type": "string"
      },
      "source": {
        "type": "string"
      }
    }
  }
}
```

Index name: `default`

#### 2. Network Access

Add your IP to Network Access whitelist or allow all IPs (0.0.0.0/0) for development.

### Running the Application

#### Option 1: Start All Services

```bash
# From project root
npm run start:all
```

#### Option 2: Start Services Separately

**Terminal 1 - Backend:**
```bash
cd src/app/api/translate
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Frontend:**
```bash
npm run dev
```

#### Option 3: Using Batch Scripts (Windows)

```bash
# Start all services
start.bat

# Stop all services
stop.ps1
```

### Access the Application

- **Frontend**: http://localhost:3000
- **Chat Interface**: http://localhost:3000/chat
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/detect` | POST | Language detection |
| `/chat/stream` | POST | RAG-enhanced streaming chat (core) |
| `/history/{id}` | GET | Get conversation history |
| `/history/clear` | POST | Clear conversation history |
| `/kb/add-pdf` | POST | Upload PDF to knowledge base |
| `/kb/pdf/{id}` | GET | Download PDF file |
| `/kb/pdfs` | GET | List all PDFs |
| `/kb/pdf/{id}` | DELETE | Delete PDF file |

## RAG Flow

```
User Input: "Tell me about scholarships"
    ↓
[1] Language Detection
    ↓
[2] Translate to English (if needed)
    ↓
[3] Generate Query Summary
    ↓
[4] MongoDB Atlas Vector Search
    ├─ Generate 768-dim embedding
    ├─ $vectorSearch aggregation
    └─ Return top 3 relevant documents
    ↓
[5] Format Context
    ↓
[6] Translate to Target Language
    ↓
[7] Stream Response (SSE)
    ↓
[8] Save to MongoDB
```

## Project Structure

```
Hackathon/
├── src/
│   └── app/
│       ├── chat/
│       │   └── page.tsx                 # Chat UI
│       └── api/
│           └── translate/
│               ├── api/
│               │   └── main.py          # FastAPI application
│               ├── core/
│               │   └── chatbot_core.py  # Translation & RAG core
│               ├── services/
│               │   └── rag_service.py   # RAG service layer
│               ├── db/
│               │   ├── connection.py    # MongoDB connection
│               │   ├── models.py        # Data models
│               │   └── gridfs_storage.py # PDF storage
│               ├── libs/
│               │   ├── language_tools.py # Language detection
│               │   └── pdf_processor.py  # PDF processing
│               ├── scripts/
│               │   └── atlas_vector_backfill.py # Vector backfill
│               ├── stream/
│               │   └── route.ts         # Next.js API proxy
│               ├── requirements.txt
│               └── .env
├── package.json
└── README.md
```

## Testing

### Test Components

```bash
cd src/app/api/translate
python test_components.py
```

This will verify:
- Environment variables
- Python dependencies
- MongoDB connections (main + Atlas)
- RAG system
- Translation engine
- GridFS storage
- API startup

### Manual API Testing

```bash
# Health check
curl http://localhost:8000/health

# Language detection
curl -X POST http://localhost:8000/detect \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'

# RAG chat (streaming)
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me about scholarships", "session_id": "test", "target_lang": "en"}'
```

## Configuration Options

### Translation Models

```env
# Use large model (8B) on GPU, small model (1B) otherwise
USE_LARGE_MODEL=0

# Quantization: dynamic | 8bit | 4bit | none
MODEL_QUANTIZATION=dynamic

# Lazy loading (load on first request)
LAZY_LOAD_MODEL=1
```

### RAG Settings

```env
# Enable/disable Atlas KB
USE_ATLAS_KB=1

# Vector Search settings
MONGODB_RAG_TOP_K=3              # Number of documents to retrieve
MONGODB_RAG_NUM_CANDIDATES=60    # Search candidates
RAG_CONTEXT_MIN_SCORE=0.55       # Minimum relevance score

# Enable fallback keyword search
MONGODB_USE_VECTOR_SEARCH=1
```

### PDF Processing

```env
PDF_DEFAULT_CHUNK_SIZE=1000      # Characters per chunk
PDF_DEFAULT_CHUNK_OVERLAP=200    # Overlap between chunks
PDF_MIN_CHUNK_SIZE=100           # Minimum chunk size
PDF_MAX_FILE_SIZE_MB=10          # Maximum file size
```

## Troubleshooting

### MongoDB Connection Issues

1. Check network access whitelist in Atlas
2. Verify connection string format
3. Ensure database and collection names match
4. Check field names match your data

### Vector Search Not Working

1. Verify Vector Search index is created and ACTIVE
2. Check embedding dimensions = 768
3. Verify embedding field exists in documents
4. System will auto-fallback to keyword search

### Model Loading Issues

1. Ensure HF_TOKEN is set correctly
2. Check internet connection for model download
3. First run may take time to download models
4. Models are cached in `~/.cache/huggingface/`

### PDF Upload Failures

1. Check file size < PDF_MAX_FILE_SIZE_MB
2. Ensure GridFS is initialized
3. Verify MongoDB connection is active

## Performance Optimization

### Backend

- **Model Quantization**: Use `dynamic` for CPU, `8bit`/`4bit` for GPU
- **Lazy Loading**: Enable for faster startup
- **Connection Pooling**: Adjust `MONGODB_POOL_SIZE`
- **Cache Size**: Tune `TRANSLATION_CACHE_SIZE`

### MongoDB Atlas

- **Index Optimization**: Ensure Vector Search index is built
- **Shard Keys**: For large datasets
- **Read Preference**: Secondary for read-heavy workloads

## Development

### Adding New Languages

1. Update `MULTI_OUTPUT_LANGS` in `.env`
2. Add translation prompt templates in `config/settings.py`
3. Add language names to `LANG_NAMES` dict

### Extending RAG

1. Modify `KnowledgeBase._atlas_retrieve()` for custom retrieval
2. Update `_atlas_format_context()` for different formatting
3. Add new metadata fields in `db/models.py`

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request


## Acknowledgments

- **Sailor2** models by sail-sg
- **MongoDB Atlas** for Vector Search capabilities
- **HuggingFace** for model hosting
- **FastAPI** framework
- **Next.js** framework
