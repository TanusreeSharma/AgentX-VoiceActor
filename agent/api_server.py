from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import tempfile
import os
import json
import re
from typing import Optional, Dict, List, Any
from pydantic import BaseModel

# Import components from our existing agent_team.py
from agno.agent import Agent
from agno.agent import AgentKnowledge
from agno.knowledge.pdf import PDFKnowledgeBase, PDFReader
from agno.vectordb.qdrant import Qdrant
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.reasoning import ReasoningTools
from agno.models.openai import OpenAIChat
from agno.embedder.openai import OpenAIEmbedder
from agno.document.chunking.document import DocumentChunking
from agno.team.team import Team

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hardcoded Qdrant configuration - update these values for your setup
QDRANT_CONFIG = {
    "url": "https://fd0f2387-645d-4d44-bb59-02909affd364.us-west-1-0.aws.cloud.qdrant.io",  # Update this
    "api_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.G6ZK06QnWMBzKXfDr0quLl_bdL7yXK1z0azfrnIpgXU",  # Update this
    "collection_name": "mydocuments",
    "reference_name": "legal_references"
}


class AnalysisResponse(BaseModel):
    analysis: str  # The main analysis markdown
    key_points: str  # The key points markdown
    negotiations: str  # The negotiations markdown


def create_legal_team(knowledge_base, reference_base):
    """Create the legal agent team"""
    legal_researcher = Agent(
        name="Legal Researcher",
        role="Legal research specialist",
        model=OpenAIChat(id="gpt-4.1"),
        tools=[DuckDuckGoTools()],
        knowledge=reference_base,
        search_knowledge=True,
        instructions=[
            "Find and cite relevant legal cases and precedents or frameworks",
            "The PRAC3 risk assessment framework is in the knowledge base, in a paper titled 'PRAC3 (Privacy, Reputation, Accountability, Consent, Credit, Compensation):Long Tailed Risks of Voice Actors in AI Data-Economy',stands for Privacy, Reputation, Accountability, Consent, Credit, Compensation",
            "Provide detailed research summaries with sources",
            "Reference specific sections from the knowledge base",
            "Always search the knowledge base for relevant information"
        ],
        show_tool_calls=True,
        markdown=True
    )

    contract_analyst = Agent(
        name="Contract Analyst",
        role="Contract analysis specialist",
        model=OpenAIChat(id="gpt-4.1"),
        knowledge=knowledge_base,
        search_knowledge=True,
        instructions=[
            "Review contracts thoroughly",
            "Always rely on the legal researcher if need any external information, such as risk assessment framework or legal precedent",
            "Identify key terms and potential issues",
            "Reference specific clauses from the document"
        ],
        markdown=True
    )

    legal_strategist = Agent(
        name="Legal Strategist",
        role="Legal strategy specialist",
        model=OpenAIChat(id="gpt-4.1"),
        knowledge=knowledge_base,
        search_knowledge=True,
        instructions=[
            "Develop comprehensive legal strategies",
            "Always rely on the legal researcher if need any external information"
            "Provide actionable negotiation strategies",
            "Consider both risks and opportunities"
        ],
        markdown=True
    )

    # Legal Agent Team
    legal_team = Team(
        name="Legal Team Lead",
        mode="coordinate",
        model=OpenAIChat(id="gpt-4.1"),
        tools=(ReasoningTools(
            think=True,
            analyze=True,
            add_instructions=True,
            add_few_shot=True,
        ),),
        members=[legal_researcher, contract_analyst, legal_strategist],
        knowledge=knowledge_base,
        search_knowledge=True,
        add_datetime_to_instructions=True,
        instructions=[
            "Coordinate analysis between team members",
            "Always transfer the task to the legal researcher if need for external information, such as risk assessment framework or legal precedent",
            "Provide comprehensive responses",
            "Ensure all negotiation strategies are properly sourced",
            "Reference specific parts of the uploaded document",
            "Always search the knowledge base before delegating tasks"
        ],
        show_tool_calls=True,
        debug_mode=True,
        show_members_responses=True,
        markdown=True
    )

    return legal_team


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_contract(
    file: UploadFile = File(...),
    openai_api_key: str = Form(...),
    analysis_type: str = Form(...),
    custom_query: Optional[str] = Form(None)
):
    """Analyze uploaded contract using the legal agent team"""

    print(f"Received analysis request: {analysis_type}")
    print(f"File: {file.filename}, Size: {file.size}")

    # Validate inputs
    if not all([openai_api_key]):
        raise HTTPException(
            status_code=400, detail="Missing required API credentials")

    # Set environment variable
    os.environ['OPENAI_API_KEY'] = openai_api_key

    # Initialize Qdrant
    try:
        vector_db = Qdrant(
            collection=QDRANT_CONFIG["collection_name"],
            url=QDRANT_CONFIG["url"],
            api_key=QDRANT_CONFIG["api_key"],
            embedder=OpenAIEmbedder(
                id="text-embedding-3-small",
                api_key=openai_api_key
            )
        )
        print("Successfully connected to Qdrant")

        # Create reference database
        reference_db = Qdrant(
            collection=QDRANT_CONFIG["reference_name"],
            url=QDRANT_CONFIG["url"],
            api_key=QDRANT_CONFIG["api_key"],
            embedder=OpenAIEmbedder(
                id="text-embedding-3-small",
                api_key=openai_api_key
            )
        )
        print("Successfully connected to Reference Qdrant")
    except Exception as e:
        print(f"Qdrant connection error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to connect to Qdrant: {str(e)}")

    # Create reference knowledge base
#     print("Creating reference knowledge base...")

    # Load documents into reference base
#     print("Loading documents into reference base...")
#     reference_base.load(recreate=False, upsert=False)

    # Save uploaded file
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
            print(f"Saved file to: {temp_file_path}")
    except Exception as e:
        print(f"File save error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

    try:
        # Create knowledge base
        print("Creating knowledge base...")
        knowledge_base = PDFKnowledgeBase(
            path=temp_file_path,
            vector_db=vector_db,
            reader=PDFReader(),
            chunking_strategy=DocumentChunking(
                chunk_size=1000,
                overlap=200
            )
        )
        reference_base = PDFKnowledgeBase(
            path=temp_file_path,
            vector_db=reference_db,
            reader=PDFReader(),
            chunking_strategy=DocumentChunking(
                chunk_size=1000,
                overlap=200
            )
        )

        # Load documents
        print("Loading documents into knowledge base...")
        knowledge_base.load(recreate=True, upsert=True)
        print("Documents loaded successfully")

        # Create legal team
        print("Creating legal team...")
        legal_team = create_legal_team(knowledge_base, reference_base)

        # Prepare query based on analysis type
        analysis_configs = {
            "Contract Review": {
                "query": "Review this contract and identify key terms, obligations, and potential issues.",
                "agents": ["Contract Analyst"],
                "description": "Detailed contract analysis focusing on terms and obligations"
            },
            "Legal Research": {
                "query": "Research relevant cases and precedents related to this document.",
                "agents": ["Legal Researcher"],
                "description": "Research on relevant legal cases and precedents"
            },
            "Risk Assessment": {
                "query": "Analyze potential legal risks and liabilities in the uploaded document based on common risk assessment frameworks such as NIST, OWASP and PRAC3. The PRAC3 risk assessment framework is in Legal Researcher's knowledge base.",
                "agents": ["Legal Researcher", "Contract Analyst", "Legal Strategist"],
                "description": "Combined risk analysis and strategic assessment"
            },
            "Compliance Check": {
                "query": "Check this document for regulatory compliance issues.",
                "agents": ["Legal Researcher", "Contract Analyst", "Legal Strategist"],
                "description": "Comprehensive compliance analysis"
            },
            "Custom Query": {
                "query": None,
                "agents": ["Legal Researcher", "Contract Analyst", "Legal Strategist"],
                "description": "Custom analysis using all available agents"
            }
        }

        config = analysis_configs.get(
            analysis_type, analysis_configs["Custom Query"])

        # Build query exactly like agent_team.py
        if analysis_type == "Risk Assessment":
            combined_query = f"""
            Using the uploaded document as reference:

            Primary Analysis Task: {analysis_configs[analysis_type]['query']}
            Focus Areas: {', '.join(analysis_configs[analysis_type]['agents'])}

            Please provide your response in exactly two sections:

            ## Risk Review
            - Identify and analyze all potential legal risks and liabilities
            - Reference specific clauses or sections from the document
            - Categorize risks by severity and likelihood
            - Include compliance and regulatory risks

            ## Scoring
            Present a risk scoring table in markdown format with the following columns:
            | Risk Category | Description | Severity (1-10) | Likelihood (1-10) | Overall Score | Mitigation Priority |

            Please search the knowledge base and provide specific references from the document.
            """
        elif analysis_type != "Custom Query":
            combined_query = f"""
            Using the uploaded document as reference:

            Primary Analysis Task: {config['query']}
            Focus Areas: {', '.join(config['agents'])}

            Please search the knowledge base and provide specific references from the document.
            """
        else:
            combined_query = f"""
            Using the uploaded document as reference:

            {custom_query}

            Please search the knowledge base and provide specific references from the document.
            Focus Areas: {', '.join(config['agents'])}
            """

        print(f"Running analysis with query type: {analysis_type}")
        # Run analysis
        response = legal_team.run(combined_query)

        if analysis_type == "Risk Assessment":
            response_content = response.content if response.content else ""
            if not response_content:
                for message in response.messages:
                    if message.role == 'assistant' and message.content:
                        analysis_content = message.content
                        break
            # Split content by sections
            sections = response_content.split("## Scoring")
            risk_review_content = sections[0].replace(
                "## Risk Review", "").strip()
            scoring_content = sections[1].strip() if len(
                sections) > 1 else "No scoring data available."

            return AnalysisResponse(
                analysis=risk_review_content,
                key_points=scoring_content,
                negotiations=""
            )
        else:

            # Extract the main analysis content
            analysis_content = ""
            if response.content:
                analysis_content = response.content
            else:
                for message in response.messages:
                    if message.role == 'assistant' and message.content:
                        analysis_content = message.content
                        break

            print("Main analysis complete")

            # Second call: Key Points
            print("Extracting key points...")
            key_points_query = f"""Based on this previous analysis:
            {analysis_content}

            Please summarize the key points in bullet points.
            Focus on insights from: {', '.join(config['agents'])}"""

            key_points_response = legal_team.run(key_points_query)

            key_points_content = ""
            if key_points_response.content:
                key_points_content = key_points_response.content
            else:
                for message in key_points_response.messages:
                    if message.role == 'assistant' and message.content:
                        key_points_content = message.content
                        break

            # Third call: Negotiations
            print("Generating negotiation strategies...")
            negotiations_query = f"""Based on this previous analysis:
            {analysis_content}

            What are your key negotiation strategies and positions based on the analysis? What negotiation points should be prioritized and what tactical approaches would be most effective?
            Provide specific negotiation strategies from: {', '.join(config['agents'])}"""

            negotiations_response = legal_team.run(negotiations_query)

            negotiations_content = ""
            if negotiations_response.content:
                negotiations_content = negotiations_response.content
            else:
                for message in negotiations_response.messages:
                    if message.role == 'assistant' and message.content:
                        negotiations_content = message.content
                        break

            # Now parse all three responses together
            print("Parsing combined responses...")

            return AnalysisResponse(
                analysis=analysis_content,
                key_points=key_points_content,
                negotiations=negotiations_content
            )

    except Exception as e:
        print(f"Analysis error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        # Clean up
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                print(f"Cleaned up temp file: {temp_file_path}")
            except:
                pass


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Legal Document Analyzer API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)
