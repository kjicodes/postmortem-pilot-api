from django.conf import settings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List
from celery import shared_task
from incidents.models import Incident, Document
import boto3
import io
import pdfplumber
from docx import Document as DocxDocument


class IncidentReport(BaseModel):
    title: str = Field(description="A short, descriptive summary. Keep it under 10 words.")
    description: str = Field(description="2-3 sentences on what failed and the impact.")
    root_cause: str = Field(description="2-3 sentences on the underlying cause.")
    affected_systems: List[str] = Field(description="List of impacted services or components.")
    severity: str = Field(description="One of: NORMAL, HIGH, CRITICAL.")
    timeline: str = Field(description="Sequence of events, no more than 5 bullet points.")
    suggested_fixes: str = Field(description="Steps to resolve the incident, no more than 5 bullet points.")
    prevention: str = Field(description="Steps to prevent recurrence, no more than 3 bullet points.")

@shared_task(bind=True)
def process_incident(self, uuid):
    try:
        incident = Incident.objects.get(uuid=uuid)
    except Incident.DoesNotExist:
        return

    print(f"Raw input: {incident.raw_input}")

    #LangChain LLM - define model to use, initialize chat, and initialize embeddings
    llm_model = "gpt-4o-mini"
    chat = ChatOpenAI(temperature=0.0, model=llm_model)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    try:
        #set instructions for llm to format output into json using IncidentReport class
        output_parser = PydanticOutputParser(pydantic_object=IncidentReport)
        format_instructions = output_parser.get_format_instructions()
        prompt = """You are an experienced software engineer supporting a technology product, with an understanding of solving incidents. 
            Imagine that you are drafting an incident report for an error. 
            Using the following stack trace or error log provided below, generate a structured incident post-mortem report.
                
            Stack trace or error log: {text}
            {format_instructions}
            """

        # Initialize prompt template using prompt created
        prompt_template = ChatPromptTemplate.from_template(prompt)
        messages = prompt_template.format_messages(text=incident.raw_input, format_instructions=format_instructions)
        #prints full prompt - test
        # print(messages[0].content)

        response = chat.invoke(messages)
        # print(response.content)

        #dictionary response
        output_dict = output_parser.parse(response.content)

        incident.title = output_dict.title
        incident.description = output_dict.description
        incident.root_cause = output_dict.root_cause
        incident.affected_systems = output_dict.affected_systems
        incident.severity = output_dict.severity
        incident.timeline = output_dict.timeline
        incident.suggested_fixes = output_dict.suggested_fixes
        incident.prevention = output_dict.prevention

        # create embeddings for the raw input to allow for vector similarity search
        # allows user to query for similar incidents
        vector = embeddings.embed_query(incident.raw_input)
        incident.vector = vector
        incident.status = Incident.Status.COMPLETED
        incident.save(update_fields=["title", "description", "root_cause", "affected_systems",
                                     "severity", "timeline", "suggested_fixes", "prevention", "status", "vector",
                                     ])
    except Exception as e:
        incident.status = Incident.Status.FAILED
        incident.save(update_fields=["status"])


@shared_task(bind=True)
def process_document(self, uuid):
    try:
        document = Document.objects.get(uuid=uuid)
    except Document.DoesNotExist:
        return

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        response = s3_client.get_object(Bucket=settings.AWS_BUCKET_NAME, Key=document.s3_key)
        file_content = response['Body'].read()

        print("After getting document from s3 bucket")
        if document.file_type == Document.FileType.PDF:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                extracted_text = ""
                for page in pdf.pages:
                    extracted_text += page.extract_text() or ""
            print("After extracting text from pdf")
            document.extracted_text = extracted_text
        elif document.file_type == Document.FileType.DOCX:
            docx = DocxDocument(io.BytesIO(file_content))
            extracted_text = ""
            for paragraph in docx.paragraphs:
                extracted_text += paragraph.text + "\n"
            print("After extracting text from docx")
        else:
            raise ValueError(f"Unsupported file type: {document.file_type}")

        #generate embeddings from extracted text
        vector = embeddings.embed_query(extracted_text)

        #save values to db
        document.extracted_text = extracted_text
        document.vector = vector
        document.status = Document.Status.COMPLETED
        document.save(update_fields=["extracted_text", "vector", "status"])
        print("Document saved")
    except Exception as e:
        document.status = Document.Status.FAILED
        document.save(update_fields=["status"])
        print(f"Document failed: {type(e).__name__}: {e}")











