# GenAI-Powered Financial Document Intelligence System 🏦

## Business Problem Statement
Financial analysts and professionals often spend hours manually scanning through hundreds of pages of bank statements, invoices, audit reports, and loan agreements to find specific numbers, clauses, or summaries. This manual extraction is error-prone, tedious, and unscalable in enterprise environments.

## Solution Overview
This project provides an enterprise-grade Generative AI application that automates financial document analysis. It allows users to upload various financial documents (both digital PDFs and scanned images), extracts the text, and leverages **Retrieval-Augmented Generation (RAG)** to answer complex queries strictly based on the provided documents. Every answer is fully explainable and includes an exact source citation (document name & page number).

## Architecture
```text
[PDF/Image Upload] 
       │
       ▼
[OCR & Text Extraction] (pdfplumber + Tesseract)
       │
       ▼
[Text Chunking] (RecursiveCharacterTextSplitter)
       │
       ▼
[Embedding Generation] (OpenAI text-embedding-3-small)
       │
       ▼
[Vector Database] (ChromaDB)
       │
       ▼
[Retriever (RAG)] <───User Query
       │
       ▼
[LLM (OpenAI GPT-3.5-turbo)]
       │
       ▼
[Answer + Source Citation] -> Streamlit UI
```

## Tech Stack
- **Programming Language**: Python
- **Frontend/UI**: Streamlit
- **LLM Framework**: LangChain
- **LLM / Embeddings**: OpenAI (`gpt-3.5-turbo`, `text-embedding-3-small`)
- **OCR / Parsing**: pytesseract, pdfplumber
- **Vector Database**: ChromaDB (Local persistent)

## Folder Structure
```text
GenAI-Financial-Doc-Intelligence/
│
├── .env                    # API keys securely stored
├── requirements.txt        # Python dependencies
├── README.md               # Documentation
├── app.py                  # Main Streamlit UI application
│
└── src/                    # Core Modules
    ├── __init__.py
    ├── ocr_utils.py        # Tesseract-based image OCR
    ├── document_loader.py  # PDF and Image parsing logic
    ├── chunking.py         # Text chunking logic
    ├── embeddings.py       # Embedding generation logic
    ├── vector_store.py     # ChromaDB interactions
    └── rag_pipeline.py     # QA/RAG retrieval chain logic
```

## Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone <your-repo-link>
   cd GenAI-Financial-Doc-Intelligence
   ```

2. **Install Dependencies**
   Make sure you have Python 3.9+ installed.
   ```bash
   pip install -r requirements.txt
   ```
   *Note: For OCR features, ensure [Tesseract](https://github.com/tesseract-ocr/tesseract) is installed on your system and added to your PATH.*

3. **Configure Environment Variables**
   The `.env` file is already created. Add your OpenAI API key if not already present:
   ```text
   OPENAI_API_KEY=your-api-key-here
   ```

4. **Run the Application**
   ```bash
   streamlit run app.py
   ```

## Sample User Queries
- *"What is the total amount due on the Q3 Invoice?"*
- *"Based on the loan agreement, what is the default interest rate?"*
- *"Summarize the risks mentioned in the 2023 Audit Report."*
- *"Who are the signatories on page 3 of the contract?"*

## Screenshots
*(Add screenshots of your working Streamlit application here)*
- **Upload Screen**: Users uploading PDFs and Images.
- **RAG Chat**: The conversational interface answering a financial question with exact document and page number sourcing.
