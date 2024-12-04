import os
import uuid
from dotenv import load_dotenv
import streamlit as st
from pymongo import MongoClient
from langchain.chains import LLMChain
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from PyPDF2 import PdfReader
from src.prompt import *
from langchain_groq import ChatGroq
from pinecone import Pinecone

# Streamlit Page Config (HARUS DI ATAS)
st.set_page_config(page_title="Doctor AI Chatbot", layout="wide")

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
try:
    db = client["medical_chatbot"]
    collection = db["chat_history"]
    print("MongoDB connected successfully.")
except Exception as e:
    st.error(f"Failed to connect to MongoDB: {e}")

# Pinecone and Groq configuration
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
os.environ["GROQ_API_KEY"] = GROQ_API_KEY
os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY

embeddings = download_hugging_face_embeddings()
index_name = "medical-chatbot"

# Initialize Pinecone
pinecone_instance = Pinecone(api_key=PINECONE_API_KEY)

docsearch = PineconeVectorStore.from_existing_index(index_name=index_name, embedding=embeddings)
retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 3})

llm = ChatGroq(model="gemma-7b-it", temperature=1, max_tokens=1024, verbose=True)

prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{history}\nUser: {input}")])
memory = ConversationBufferMemory(memory_key="history", input_key="input", return_messages=True)

conversation_chain = LLMChain(llm=llm, prompt=prompt, memory=memory, verbose=True)

# Helper functions
def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    text = "".join([page.extract_text() for page in reader.pages])
    return text

def save_to_mongo(user_input, bot_response, session_id):
    collection.insert_one({"session_id": session_id, "user_input": user_input, "bot_response": bot_response})

def get_session_id():
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    return st.session_state["session_id"]

# Streamlit App
def main():
    st.sidebar.title("Doctor AI - Part of CareSense Project")
    st.sidebar.info("Providing AI-powered healthcare assistance.")

    st.title("Doctor AI - Your Health Assistant")

    # Upload PDF Section
    st.header("Upload Document (PDF)")
    uploaded_file = st.file_uploader("Select a PDF file", type=["pdf"])

    if uploaded_file is not None:
        if uploaded_file.type == "application/pdf":
            pdf_content = extract_text_from_pdf(uploaded_file)
            st.success(f"File '{uploaded_file.name}' uploaded successfully.")
            st.text_area("Extracted PDF Content", pdf_content, height=200)
            st.session_state["document_content"] = pdf_content

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    if "document_content" not in st.session_state:
        st.session_state["document_content"] = ""

    st.subheader("Chat History")
    chat_history_container = st.container()

    with chat_history_container:
        for chat in st.session_state["chat_history"]:
            st.chat_message("user").write(chat['user_input'])
            st.chat_message("assistant").write(chat['bot_response'])

    with st.form(key="user_input_form", clear_on_submit=True):
        user_input = st.text_input("Type your message here:")
        submit_button = st.form_submit_button("Send")

    if submit_button and user_input:
        with chat_history_container:
            st.chat_message("user").write(user_input)

        memory.chat_memory.add_user_message(user_input)
        context = st.session_state["document_content"]
        response = conversation_chain({"input": user_input, "context": context})
        bot_response = response["text"]
        memory.chat_memory.add_ai_message(bot_response)

        with chat_history_container:
            st.chat_message("assistant").write(bot_response)

        st.session_state["chat_history"].append({"user_input": user_input, "bot_response": bot_response})
        session_id = get_session_id()
        save_to_mongo(user_input, bot_response, session_id)


if __name__ == "__main__":
    main()
