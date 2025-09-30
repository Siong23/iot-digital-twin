# query.py
from langchain_community.vectorstores import Chroma
from sentence_transformers import SentenceTransformer
from langchain_ollama import OllamaLLM

# -------- CONFIG --------
DB_DIR = "./chroma_db"          # same path as in ingest.py
MODEL_NAME = "all-MiniLM-L6-v2" # must match ingest.py
TOP_K = 3                       # number of most relevant chunks
OLLAMA_MODEL = "llama3"         # change to the Ollama model you installed
# -------------------------

def main():
    print("⚡ Loading embedding model...")
    embedder = SentenceTransformer(MODEL_NAME)

    print("⚡ Connecting to Chroma DB...")
    db = Chroma(
        persist_directory=DB_DIR,
        embedding_function=embedder
    )

    llm = OllamaLLM(model=OLLAMA_MODEL)

    print("✅ Ready! Type your questions (or 'exit' to quit)\n")

    while True:
        query = input("❓ Question: ")
        if query.lower() in ["exit", "quit", "q"]:
            break

        results = db.similarity_search(query, k=TOP_K)

        # Build context from retrieved docs
        context = "\n\n".join([doc.page_content for doc in results])

        prompt = f"""You are an AI assistant for an IoT digital twin system.
Use the following context to answer the question clearly and concisely.

Context:
{context}

Question: {query}
Answer:"""

        print("\n🤖 Thinking...\n")
        answer = llm.invoke(prompt)
        print(f"💡 {answer}\n")

if __name__ == "__main__":
    main()
