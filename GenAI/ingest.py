# query.py
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM

# -------- CONFIG --------
DB_DIR = "chroma_db"          
MODEL_NAME = "all-MiniLM-L6-v2" 
TOP_K = 3                       
OLLAMA_MODEL = "llama3.1:8b"         
# -------------------------

def main():
    print("⚡ Loading embedding model...")
    embedder = HuggingFaceEmbeddings(model_name=MODEL_NAME)

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
