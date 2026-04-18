import asyncio
import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "KG RAG API"
    debug: bool = False
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr
    openai_api_key: SecretStr
    llm_model: str = "gpt-5.4-mini"


settings = Settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)

graph: Neo4jGraph | None = None
chain: GraphCypherQAChain | None = None


@app.on_event("startup")
def startup():
    global graph, chain
    logger.info("Connecting to Neo4j at {}", settings.neo4j_uri)
    graph = Neo4jGraph(
        url=settings.neo4j_uri,
        username=settings.neo4j_user,
        password=settings.neo4j_password.get_secret_value(),
    )
    graph.refresh_schema()
    logger.info("Neo4j schema: {}", graph.schema)

    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key.get_secret_value(),
    )
    chain = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        return_intermediate_steps=True,
        verbose=settings.debug,
        allow_dangerous_requests=True,
    )
    logger.info("GraphCypherQAChain ready")


class ChatRequest(BaseModel):
    message: str


def format_response(result: dict) -> str:
    parts: list[str] = []

    steps = result.get("intermediate_steps", [])
    if steps:
        cypher_query = steps[0].get("query", "") if len(steps) > 0 else ""
        context = steps[1].get("context", []) if len(steps) > 1 else []

        if cypher_query:
            parts.append(f"### Generated Cypher Query\n\n```cypher\n{cypher_query}\n```")

        if context:
            parts.append(f"### Graph Results\n\n```json\n{json.dumps(context, indent=2, default=str)}\n```")

    answer = result.get("result", "No answer generated.")
    parts.append(f"### Analysis\n\n{answer}")

    return "\n\n".join(parts)


async def generate_stream(message: str):
    try:
        result = await asyncio.to_thread(chain.invoke, {"query": message})
        response = format_response(result)
    except Exception as e:
        logger.error("Chain error: {}", e)
        response = f"**Error querying knowledge graph:** {e}"

    words = response.split(" ")
    for i, word in enumerate(words):
        token = word if i == 0 else " " + word
        yield f"data: {json.dumps({'token': token})}\n\n"
        await asyncio.sleep(0.01)
    yield "data: [DONE]\n\n"


@app.post("/api/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        generate_stream(req.message),
        media_type="text/event-stream",
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
