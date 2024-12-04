from groq import Groq
import streamlit as st
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from langchain_groq import ChatGroq
from langchain.chains import LLMChain
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate
from pymongo import MongoClient
from dotenv import load_dotenv
import uuid
import os
from src.prompt import *
from pinecone import Pinecone
from PyPDF2 import PdfReader

load_dotenv()

# MongoDB configuration
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["medical_chatbot"]
collection = db["chat_history"]

PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

os.environ["GROQ_API_KEY"] = GROQ_API_KEY
os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY

embeddings = download_hugging_face_embeddings()

index_name = "medical-chatbot"

# Initialize Pinecone
pinecone_instance = Pinecone(api_key=PINECONE_API_KEY)

# Check and create index if it doesn't exist
if index_name not in pinecone_instance.list_indexes().names():
    pinecone_instance.create_index(
        name=index_name,
        dimension=384,  # Match your embedding dimension
        metric='cosine'
    )

# Initialize the document searcher
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
        ("human", "{history}\nUser: {input}"),
    ]
)

# Initialize memory to store conversation context
memory = ConversationBufferMemory(
    memory_key="history",
    input_key="input",
    return_messages=True
)

# Create an LLM chain that includes memory
conversation_chain = LLMChain(
    llm=llm,
    prompt=prompt,
    memory=memory,
    verbose=True
)

def get_session_id():
    # Check if a session ID already exists; otherwise, create a new one.
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())  # Generate a unique session ID
    return st.session_state["session_id"]

def save_to_mongo(user_input, bot_response, session_id):
    collection.insert_one({
        "session_id": session_id,
        "user_input": user_input,
        "bot_response": bot_response
    })

# Function to read and extract text from a PDF file
def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

# Streamlit App
def main():
    st.set_page_config(page_title="Doctor AI Chatbot", layout="wide")

    # Handle API requests
    if st.request.method == 'POST':
        try:
            # Read JSON request
            user_input = st.request.json.get('user_input')
            if not user_input:
                st.error("Invalid request")
            else:
                response = {"bot_response": f"Response to '{user_input}'"}
                st.json(response)
        except Exception as e:
            st.error(f"Error processing request: {e}")

    # Sidebar information
    st.sidebar.title("Doctor AI")
    st.sidebar.info("Doctor AI is a chatbot that provides information about diseases, health conditions, and medical information. Part of CareSense project created by President University Informatics Students. The project is focused on AI in Healthcare to provide advisement to patients who are unable to go to a doctor by giving a recomendations and consultation for commons diseases (except fatal diseases).")
    st.sidebar.title("CareSense")
    st.sidebar.info("CareSense is focused on AI in Healthcare, founded by President University Informatics Students.")
    
    st.title("Doctor AI - Your Health Assistant")

    # PDF & Image Upload Section
    st.header("Upload Document (PDF)")
    uploaded_file = st.file_uploader("Select a PDF file", type=["pdf"])

    if uploaded_file is not None:
        if uploaded_file.type == "application/pdf":
            # Extract text from the uploaded PDF
            pdf_content = extract_text_from_pdf(uploaded_file)
            st.success(f"File '{uploaded_file.name}' uploaded successfully.")
            st.write("### Extracted PDF Content")
            st.text_area("Content from PDF", pdf_content, height=200)
            st.session_state["document_content"] = pdf_content

    # Initialize session state for chat history and document content if they don't exist
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    if "document_content" not in st.session_state:
        st.session_state["document_content"] = ""

    # Display the conversation history
    st.subheader("Chat History")
    chat_history_container = st.container()

    # Display chat history from session state
    with chat_history_container:
        for chat in st.session_state["chat_history"]:
            st.chat_message("user").write(f"{chat['user_input']}")
            st.chat_message("assistant").write(f"{chat['bot_response']}")

    # Form for user input
    with st.form(key='user_input_form', clear_on_submit=True):
        user_input = st.text_input("Type your message here:")
        submit_button = st.form_submit_button("Send")
    
    if submit_button and user_input:
        # Display user message
        with chat_history_container:
            st.chat_message("user").write(f"{user_input}")

        # Update memory with user input
        memory.chat_memory.add_user_message(user_input)

        # Use the stored document content as part of the context
        context = st.session_state["document_content"] if st.session_state["document_content"] else ""

        # Invoke conversation chain with user message, history, and persistent context
        response = conversation_chain({"input": user_input, "context": context})
        bot_response = response["text"]

        # Update memory with bot response
        memory.chat_memory.add_ai_message(bot_response)

        # Display bot response
        with chat_history_container:
            st.chat_message("assistant").write(f"{bot_response}")

        # Save the conversation to session state
        st.session_state["chat_history"].append({"user_input": user_input, "bot_response": bot_response})

        # Get or create session ID
        session_id = get_session_id()

        # Save conversation to MongoDB
        save_to_mongo(user_input, bot_response, session_id)

if __name__ == "__main__":
    main()
