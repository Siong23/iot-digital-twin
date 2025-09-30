# ingest.py
import os
from pathlib import Path
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings

# -------- CONFIG --------
KNOWLEDGE_DIR = "knowledge"   # folder where JSON/txt files live
DB_DIR = "chroma_db"          # persistent Chroma storage
MODEL_NAME = "all-MiniLM-L6-v2" # embedding model
CHUNK_SIZE = 800                # characters per chunk
CHUNK_OVERLAP = 100             # overlap between chunks
# -------------------------

def load_documents():
    """Load all text/json files from KNOWLEDGE_DIR"""
    docs = []
    for file_path in Path(KNOWLEDGE_DIR).glob("*"):
        if file_path.suffix.lower() in [".txt", ".json", ".log", ".cfg"]:
            loader = TextLoader(str(file_path), encoding="utf-8")
            docs.extend(loader.load())
    return docs

def split_documents(docs):
    """Split documents into chunks"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )
    return splitter.split_documents(docs)

def main():
    print(f"🔍 Loading docs from {KNOWLEDGE_DIR}...")
    docs = load_documents()
    print(f"✅ Loaded {len(docs)} documents")

    print("✂️ Splitting into chunks...")
    chunks = split_documents(docs)
    print(f"✅ Created {len(chunks)} chunks")

    print(f"⚙️ Loading embedding model: {MODEL_NAME}...")
    embedder = HuggingFaceEmbeddings(model_name=MODEL_NAME)

    print("📥 Creating Chroma index...")
    db = Chroma.from_documents(
        documents=chunks,
        embedding=embedder,           # ✅ correct parameter
        persist_directory=DB_DIR
    )
    db.persist()

    print(f"🎉 Done! Knowledge base stored in {DB_DIR}")

if __name__ == "__main__":
    main()
