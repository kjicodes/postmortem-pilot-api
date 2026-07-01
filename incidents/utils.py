from langchain_openai import OpenAIEmbeddings
from docx import Document as DocxDocument
import io
import pdfplumber


#generate vector to allow for vector similarity search for incidents
def generate_embedding(text):
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vector = embeddings.embed_query(text)
    return vector

def extract_document_text(file_type, file_content):
    extracted_text = ""
    if file_type == "pdf":
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                extracted_text += page.extract_text() or ""
    elif file_type == "docx":
        docx = DocxDocument(io.BytesIO(file_content))
        for paragraph in docx.paragraphs:
            extracted_text += paragraph.text + "\n"
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    if not extracted_text.strip():
        raise ValueError("No text could be extracted from the file.")

    return extracted_text