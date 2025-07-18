# [🤖 AI Document Bot](https://t.me/AI_Docz_Bot)
### PDF Analysis Telegram Bot with Dual AI Support (GROQ API + Ollama Models)

<div>
 <img src="https://img.shields.io/badge/Python-3.8+-white?logo=python&logoColor=white&labelColor=3776AB&style=for-the-badge" alt="Python">
 <img src="https://img.shields.io/badge/Telegram-Bot-white?logo=telegram&logoColor=white&labelColor=26A5E4&style=for-the-badge" alt="Telegram Bot">
 <img src="https://img.shields.io/badge/GROQ-API-white?logo=ai&logoColor=white&labelColor=FF6B35&style=for-the-badge" alt="GROQ API">
 <img src="https://img.shields.io/badge/Ollama-Local_AI-white?logo=ollama&logoColor=white&labelColor=000000&style=for-the-badge" alt="Ollama">
 <img src="https://img.shields.io/badge/FAISS-Vector_Search-white?logo=meta&logoColor=white&labelColor=0668E1&style=for-the-badge" alt="FAISS">
 <img src="https://img.shields.io/badge/PyPDF2-PDF_Processing-white?logo=adobeacrobatreader&logoColor=white&labelColor=DC143C&style=for-the-badge" alt="PyPDF2">
</div>

## 📖 Overview

AI Document Bot is *Telegram Bot* that transforms **`PDF Documents`** into interactive, queryable knowledge bases. Upload any **`PDF Document`** and ask questions about its content using either cloud-based **GROQ API** or **Local Ollama Models**.

### ✨ Key Features

- #### 📄 **`PDF Document Processing`** - extract and analyze text from pdf files (up to 20mb)
- #### 🧠 **`Dual AI Support`** - choose between groq (cloud/fast) or ollama (local/private)
- #### 🔍 **`Advanced Vector Search`** - multiple search strategies for accurate content retrieval
- #### 🛠️ **`Debug Mode`** - inspect search results and understand how the bot finds relevant information
- #### ⚙️ **`Flexible Configuration`** - switch between AI Services and Models on the fly

## 🚀 Quick Start

### 📋 Prerequisites

- **`Python 3.8+`**
- **`Telegram Bot Token`** (get from [`@botfather`](https://t.me/botfather))
- **`Groq API Key`** (optional, get from [`groq.com`](https://groq.com))
- **`Ollama`** (optional, for local ai - [`ollama.ai`](https://ollama.ai))

> [!NOTE]
> #### *To experience the Bot in Action*, access it on Telegram via [`@AI_Docz_Bot`](https://t.me/AI_Docz_Bot). No `GROQ API Key` or `Ollama Model` is required.

### ⚙️ Installation

#### 1. **Clone the Repository:**
```bash
git clone https://github.com/jafarbekyusupov/ai-docs-tgbot.git
cd ai-docs-tgbot
```

#### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate
```
> [!TIP]
> **On Windows:**
> ```
> python -m venv venv
> venv\Scripts\activate
> ```

#### 3. Install Dependencies:
```bash
pip install -r requirements.txt
```

#### 4. Configure Environment Variables:
Create a `.env` file in the ***root directory:***
```.env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GROQ_API_KEY=your_groq_api_key_here  # optional
```
#### 5. Setup Ollama *(Optional)*:

##### Install Ollama from https://ollama.ai
```bash
ollama pull llama3.2  # or any other model you prefer
```
#### 6. Run the Bot:
```bash
python run.py
```
## 🎯 Usage

### 🔧 Basic Workflow

1. **Start the Bot** - send `/start` to see welcome message
2. **Configure AI Service (Optional)** - use `/settings` to choose between `Groq` or `Ollama` *(`GROQ` is set as default)*
3. **Upload PDF** - send any PDF Document *(Max 20MB - telegram's limit)*
4. **Ask Questions** - start asking **Questions** about your **Document Content**

### 📱 Available Commands
| Command | Description |
|---------|-------------|
| `/start` | show welcome message and basic instructions |
| `/settings` | choose between groq and ollama ai services |
| `/models` | list and switch between available ollama models |
| `/status` | check ai services status and current configuration |
| `/clear` | clear current document and start over |
| `/debug <query>` | see detailed search results for debugging |
| `/help` | show help information |

### 🤖 AI Service Options

#### ☁️ Groq (Cloud AI/LLM)
- **pros:** fast response times, no local setup required
- **cons:** requires api key, sends data to cloud
- **models:** llama3-8b-8192 (default)

#### 🏠 Ollama (Local AI/LLM)
- **pros:** completely private, no api costs, multiple model choices
- **cons:** slower response times, requires local installation
- **models:** llama3.2, mistral, codellama, and many more

## 🏗️ Architecture & Structure

### 📁 Project Structure
```
ai-docs-tgbot/
├── config.py                 # configuration and environment variables
├── run.py                    # application entry point
├── document_bot.py           # main bot class and setup
├── bot_handlers.py           # telegram message and callback handlers
├── document_processor.py     # pdf text extraction and segmentation
├── ai_processor.py           # groq and ollama ai integration
├── vector_search.py          # faiss-based semantic search
├── ollama.py                 # ollama client implementation
├── requirements.txt          # python dependencies
└── .env                      # environment variables (CREATE THIS FILE ON UR OWN MACHINE)
```
### 🔄 Core Components

#### 📑 Document Processor
- extracts text from pdf files using pypdf2
- analyzes document structure and identifies headers
- segments text into meaningful chunks for better retrieval
- supports both advanced and simple segmentation strategies

#### 🔍 Vector Search
- Creates embeddings using *`sentence-transformers`*
- Implements **multiple search strategies:**
- - **Smantic Search** - finds content based on meaning
- - **Keyword Search** - matches specific terms
- - **Fuzzy Search** - handles partial matches
- - **Section Search** - searches within document sections
- Uses `faiss` for efficient similarity search

#### 🤖 AI Processor
- supports both groq and ollama apis
- handles model selection and switching
- manages api calls and error handling
- provides consistent interface for different ai services

#### 🎛️ Bot Handlers
- processes telegram messages and commands
- manages user sessions and preferences
- handles file uploads and user interactions
- provides inline keyboards for easy configuration

## 🛠️ Advanced Features

### 🔍 Multi-Strategy Search

#### Bot uses ***Four Different Search Strategies*** to find the Most Relevant Content:
> [!IMPORTANT]
> 1. **Semantic Search** - understands the meaning of your question
> 2. **Adaptive Keyword Search** - matches important document terms
> 3. **Fuzzy Matching** - finds partial word matches
> 4. **Section-Based Search** - searches within specific document sections

### 📊 Debug Mode

use `/debug <your question>` to see exactly how the bot finds relevant information:
- view search strategies and their results
- see similarity scores for different content segments
- understand why certain answers were selected

### ⚡ Intelligent Segmentation

the document processor automatically:
- identifies document headers and sections
- creates logical text segments
- preserves context across segment boundaries
- handles various document formats and structures

## 🔧 Configuration

### 🌍 Environment Variables
> [!WARNING]
> #### Required
> ```.env
> TELEGRAM_BOT_TOKEN=your_bot_token
> ```
> #### *Optional (for Groq Support)*
> ```.env
> GROQ_API_KEY=your_groq_api_key
> ```
> 
> #### *Optional (Customize Ollama URL)*
> ```.env
> OLLAMA_BASE_URL=http://localhost:11434 # or the port you set it to
> ```

### 🎛️ Runtime Configuration

> [!NOTE]
> #### Users can configure the Bot via **Telegram Commands:**
> - switch between groq and ollama
> - select different ollama models
> - view service status and availability

## 🧪 Technical Details

### 📚 Dependencies

| Package | Purpose |
|---------|---------|
| `pyTelegramBotAPI` | telegram bot framework |
| `PyPDF2` | pdf text extraction |
| `groq` | groq ai api client |
| `sentence-transformers` | text embeddings |
| `faiss-cpu` | vector similarity search |
| `numpy` | numerical computations |

### 🔒 Security Features

- no persistent storage of document content
- user sessions are memory-based only
- api keys are environment-based
- local ollama option for complete privacy

### ⚡ Performance Optimizations

- efficient text segmentation algorithms
- normalized vector embeddings for better search
- combined search strategies for improved accuracy
- fallback mechanisms for robust operation

---

<div align="center">

#### AI Docs TGBot @ [`jafarbekyusupov`](https://github.com/jafarbekyusupov)

[⭐ Star this Repo](https://github.com/jafarbekyusupov/ai-docs-tgbot) • [🐛 Report Bug](https://github.com/jafarbekyusupov/ai-docs-tgbot/issues) • [💡 Request **Feature**](https://github.com/jafarbekyusupov/ai-docs-tgbot/issues)

</div>
