from django.conf import settings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from pydantic import BaseModel, Field
from typing import List
from celery import shared_task
from incidents.models import Incident, Document, PatternReport
from incidents.utils import generate_embedding, extract_document_text
import boto3
import numpy as np
from sklearn.cluster import KMeans

LLM_MODEL = "gpt-4o-mini"

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

    #LangChain LLM - initialize chat
    chat = ChatOpenAI(temperature=0.0, model=LLM_MODEL)

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
        vector = generate_embedding(incident.raw_input)
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

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        response = s3_client.get_object(Bucket=settings.AWS_BUCKET_NAME, Key=document.s3_key)
        file_content = response['Body'].read()

        extracted_text = extract_document_text(document.file_type, file_content)
        #generate embeddings from extracted text
        vector = generate_embedding(extracted_text)

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


@shared_task(bind=True)
def generate_pattern_report(self):
    incidents = list(Incident.objects.filter(vector__isnull=False, status=Incident.Status.COMPLETED))


    #----RUN KMEANS----
    #N incidents - for KMeans clusters
    #number of clusters scale sensibly
    count = len(incidents)
    print(count)

    if count < 3:
        return
    elif count < 20:
        n = 3
    elif count < 100:
        n = 5
    else:
        n = 10

    try:
        #extract vectors into a numpy array - needed as input for KMeans
        vectors = np.array([incident.vector for incident in incidents])
        print(vectors)

        #run KMeans
        kmeans = KMeans(n_clusters=n, random_state=42)
        kmeans.fit(vectors)
        labels = kmeans.labels_
        print(labels)

        #group incidents by cluster
        clusters = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(incidents[i])    #each object key is a cluster number, which has a list of incidents as the value
        print(clusters)

        #----RUN LLM----
        #use LLM to summarize in 2 parts:
        #first summarize each cluster of incidents..
        #then summarize those summaries
        chat = ChatOpenAI(temperature=0.0, model=LLM_MODEL)
        prompt_one = """You are an experienced software engineer analyzing a group of related incidents.
            Below is a list of incident titles and descriptions that have been grouped together by similarity.
            Summarize the recurring pattern you see in 2-3 sentences. Be specific about what is failing and why.
            
            Incidents: {cluster_text}
            Pattern summary: 
            """
        prompt_two = """You are an experienced software engineer analyzing incident patterns across a system.
        Below are summaries of recurring incident patterns identified from the incident history.
        Synthesize these into a final pattern report that highlights the most critical trends, 
        recurring root causes, and recommended areas of focus. Be concise and actionable.
        Keep the final report under 300 words. Focus on the 2-3 most critical patterns only.
        
        Cluster summaries: {cluster_summaries}
        Final pattern report:
        """

        cluster_prompt = ChatPromptTemplate.from_template(prompt_one)
        synthesis_prompt = ChatPromptTemplate.from_template(prompt_two)

        cluster_chain = cluster_prompt | chat | StrOutputParser()
        synthesis_chain = synthesis_prompt | chat | StrOutputParser()

        #each entry in the list is a summary of a cluster (group of related incidents)
        cluster_summaries_list = []
        for label, cluster_incidents in clusters.items():
            incident_lines = []
            for incident in cluster_incidents:
                line = f"- {incident.title}: {incident.description}"
                incident_lines.append(line)

            #join incidents together to be summarized by llm then add to the list - repeat
            cluster_text = "\n".join(incident_lines)
            summary = cluster_chain.invoke({"cluster_text": cluster_text})
            cluster_summaries_list.append(summary)

            print(f"Incident lines summarized by llm: {incident_lines}")
        print(f"Cluster summaries list from llm: {cluster_summaries_list}")

        cluster_summaries = "\n\n".join(cluster_summaries_list)
        print(cluster_summaries)
        final_report = synthesis_chain.invoke({ "cluster_summaries": cluster_summaries })

        #build the cluster data for the response obj - provide context for the generated pattern report for anyone reading it
        cluster_data = []
        for i, (label, cluster_incidents) in enumerate(clusters.items()):
            data = {
                "cluster": i + 1,
                "incidents": [{"uuid": str(incident.uuid), "title": incident.title} for incident in cluster_incidents],
                "summary": cluster_summaries_list[i]
            }
            print(data)
            cluster_data.append(data)

        pattern_report = { "summary": final_report, "clusters": cluster_data }
        PatternReport.objects.create(report=pattern_report)
    except Exception as e:
        print(f"Pattern report generation failed: {type(e).__name__}: {e}")






















