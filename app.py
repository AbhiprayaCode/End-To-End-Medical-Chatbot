from flask import Flask, render_template, jsonify, request
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from langchain_groq import ChatGroq
from langchain.chains import LLMChain
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from src.prompt import *
import requests
import os

app = Flask(__name__)

load_dotenv()

PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

os.environ["GROQ_API_KEY"] = GROQ_API_KEY
os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY

embeddings = download_hugging_face_embeddings()

index_name = "medical-chatbot"

# Embed each chunk and upsert the embeddings into Pinecone index
docsearch = PineconeVectorStore.from_existing_index(
    index_name=index_name,
    embedding=embeddings
) 

retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 3})

llm = ChatGroq(
    model="gemma-7b-it",
    temperature=1,
    max_tokens=1024,
    verbose=True,
)

# Define prompt with expected input variables 'context' and 'input'
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        ("human", "{history}\n{context}\nUser: {input}"),
    ]
)

# Initialize memory to store conversation context
memory = ConversationBufferMemory(
    memory_key="history",  # Key used for accessing conversation history in chain
    input_key="input",     # Specifies the main input variable
    return_messages=True   # Ensures history is returned as a list of messages
)

# Create an LLM chain that includes memory
conversation_chain = LLMChain(
    llm=llm,
    prompt=prompt,
    memory=memory,
    verbose=True
)

# Print the memory history to see what context is being retained
print("Conversation History:", memory.load_memory_variables({}))

@app.route("/")
def index():
    return render_template("chat.html")

@app.route("/get", methods=["GET", "POST"])
def chat():
    msg = request.form["msg"]
    print("User Input:", msg)

    # Get documents related to the user query using retriever
    related_docs = retriever.get_relevant_documents(msg)
    
    # Format related documents into a single string for better context
    context = "\n".join([doc.page_content for doc in related_docs])

    # Invoke the conversation chain with the user message, history, and context from related documents
    response = conversation_chain({"input": msg, "context": context})

    print("Response:", response["text"])
    return str(response["text"])

# URL endpoint API Kemenkes atau data.go.id
API_URL = 'https://data.go.id/api/v1/health_data_endpoint'  # Ganti dengan endpoint aktual
API_KEY = 'YOUR_API_KEY'  # API key yang diperoleh dari registrasi (jika diperlukan)

def fetch_health_data():
    headers = {
        'Authorization': f'Bearer {API_KEY}',  # Tambahkan jika API membutuhkan authorization
        'Content-Type': 'application/json'
    }
    
    response = requests.get(API_URL, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()

@app.route('/api/health-data', methods=['GET'])
def get_health_data():
    try:
        data = fetch_health_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=8080, debug=True)

if __name__ == "__main__":
    app.run()
