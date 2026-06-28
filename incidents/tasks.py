from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List
from celery import shared_task
from incidents.models import Incident

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

    print(incident.raw_input)

    #LangChain LLM - define model to use and initialize chat
    llm_model = "gpt-4o-mini"
    chat = ChatOpenAI(temperature=0.0, model=llm_model)

    try:
        #set instructions for llm to format output into json
        output_parser = PydanticOutputParser(pydantic_object=IncidentReport)
        format_instructions = output_parser.get_format_instructions()

        #prompt
        prompt = """You are an experienced software engineer supporting a technology product, with an understanding \
                of solving incidents. Imagine that you are drafting an incident report for an error. 
                Using the following stack trace or error log provided below, \
                generate a structured incident post-mortem report.
                
                Format the output as a JSON with the following keys:
                title
                description
                root_cause
                affected_systems
                severity
                timeline
                suggested_fixes
                prevention
                
                Stack trace or error log: {text}
                {format_instructions}
                """

        # Initialize prompt template using prompt created
        prompt_template = ChatPromptTemplate.from_template(prompt)
        messages = prompt_template.format_messages(text=incident.raw_input, format_instructions=format_instructions)

        #full prompt
        print(messages[0].content)

        #get response and print content
        #used to be chat(messages)
        response = chat.invoke(messages)
        print(response.content)

        #dictionary response
        output_dict = output_parser.parse(response.content)
        print(output_dict)

        #test dict
        print(output_dict.title)

        #save data to db
        incident.title = output_dict.title
        incident.description = output_dict.description
        incident.root_cause = output_dict.root_cause
        incident.affected_systems = output_dict.affected_systems
        incident.severity = output_dict.severity
        incident.timeline = output_dict.timeline
        incident.suggested_fixes = output_dict.suggested_fixes
        incident.prevention = output_dict.prevention
        incident.status = Incident.Status.COMPLETED
        incident.save(update_fields=["title", "description", "root_cause", "affected_systems",
                                     "severity", "timeline", "suggested_fixes", "prevention", "status"
                                     ])
    except Exception as e:
        incident.status = Incident.Status.FAILED
        incident.save(update_fields=["status"])




