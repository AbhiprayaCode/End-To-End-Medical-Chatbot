from langchain.document_loaders import PyPDFLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceBgeEmbeddings
import pandas as pd

# Extract data from the PDF files
def load_pdf_file(data):
    loader = DirectoryLoader(data,
                             glob = "*.pdf",
                             loader_cls=PyPDFLoader)
    documents = loader.load()
    return documents

# Extract data from the CSV files
def load_csv_file(data):
    loader = DirectoryLoader(data,
                             glob="*.csv",
                             loader_cls=lambda file_path: pd.read_csv(data))
    documents = loader.load()
    return documents

def load_image_file(data):
    loader = DirectoryLoader(data,
                             glob="*.jpg",
                             loader_cls=PyPDFLoader)
    documents = loader.load()
    return documents

# Split the Data in Chunks
def text_split(extracted_data):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=20)
    text_chunks = text_splitter.split_documents(extracted_data)
    return text_chunks

# Download the embeddings from Hugging Face
def download_hugging_face_embeddings():
    embeddings = HuggingFaceBgeEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')
    return embeddings