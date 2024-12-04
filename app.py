from flask import Flask, request, jsonify
from flask_cors import CORS
from langchain.chains import LLMChain
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import uuid
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from langchain_groq import ChatGroq

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["medical_chatbot"]
collection = db["chat_history"]

# Initialize Pinecone and LLM
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
os.environ["GROQ_API_KEY"] = GROQ_API_KEY
os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY

embeddings = download_hugging_face_embeddings()
index_name = "medical-chatbot"
docsearch = PineconeVectorStore.from_existing_index(
    index_name=index_name, embedding=embeddings
)
retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 3})

llm = ChatGroq(
    model="gemma-7b-it", temperature=1, max_tokens=1024, verbose=True
)

prompt = ChatPromptTemplate.from_messages(
    [("system", "You are a helpful AI."), ("human", "{history}\n{context}\nUser: {input}")]
)

memory = ConversationBufferMemory(
    memory_key="history", input_key="input", return_messages=True
)

conversation_chain = LLMChain(
    llm=llm, prompt=prompt, memory=memory, verbose=True
)


@app.route("/api/chat", methods=["POST"])
def chat_endpoint():
    data = request.get_json()
    user_input = data.get("message", "")

    # Retrieve relevant documents
    related_docs = retriever.get_relevant_documents(user_input)
    context = "\n".join([doc.page_content for doc in related_docs])

    # Generate response
    response = conversation_chain({"input": user_input, "context": context})
    bot_response = response["text"]

    # Save conversation to MongoDB
    session_id = str(uuid.uuid4())
    collection.insert_one({
        "session_id": session_id,
        "user_input": user_input,
        "bot_response": bot_response
    })

    # Return response
    return jsonify({"response": bot_response})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501)
