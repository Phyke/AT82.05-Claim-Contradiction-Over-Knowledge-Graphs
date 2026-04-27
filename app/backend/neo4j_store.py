import time

from loguru import logger
from neo4j import GraphDatabase

from config import settings

INSERT_QUERY = """
MERGE (d:Document {doc_id: $doc_id})
SET d.text = $text,
    d.preview = $preview,
    d.n_chunks = $n_chunks,
    d.n_triples = $n_triples,
    d.created_at = coalesce(d.created_at, $created_at)
WITH d
UNWIND $chunks AS ch
  MERGE (c:Chunk {doc_id: $doc_id, sentence_id: ch.sentence_id})
  SET c.source_text = ch.source_text,
      c.embedding = ch.embedding
  MERGE (d)-[:CONTAINS]->(c)
  WITH d, c, ch
  UNWIND ch.triples AS t
    MERGE (s:Entity {doc_id: $doc_id, name: t.s})
    MERGE (o:Entity {doc_id: $doc_id, name: t.o})
    MERGE (c)-[:MENTIONS]->(s)
    MERGE (c)-[:MENTIONS]->(o)
    CREATE (s)-[:RELATION {
      predicate: t.p,
      sentence_id: ch.sentence_id,
      doc_id: $doc_id,
      polarity: t.polarity,
      polarity_marker: t.polarity_marker,
      modality: t.modality,
      modality_marker: t.modality_marker,
      attribution: t.attribution,
      quantity: t.quantity
    }]->(o)
"""

S_SR = """
MATCH (s:Entity {doc_id: $doc_id})-[r1:RELATION {doc_id: $doc_id}]->(o1:Entity {doc_id: $doc_id})
MATCH (s)-[r2:RELATION {doc_id: $doc_id}]->(o2:Entity {doc_id: $doc_id})
WHERE r1.predicate = r2.predicate
  AND elementId(r1) < elementId(r2)
  AND r1.sentence_id <> r2.sentence_id
  AND (
    o1.name <> o2.name
    OR (r1.quantity IS NOT NULL AND r2.quantity IS NOT NULL AND r1.quantity <> r2.quantity)
  )
RETURN DISTINCT r1.sentence_id AS sid_a, r2.sentence_id AS sid_b
"""

S_SO = """
MATCH (s:Entity {doc_id: $doc_id})-[r1:RELATION {doc_id: $doc_id}]->(o:Entity {doc_id: $doc_id})
MATCH (s)-[r2:RELATION {doc_id: $doc_id}]->(o)
WHERE elementId(r1) < elementId(r2)
  AND r1.sentence_id <> r2.sentence_id
  AND (r1.predicate <> r2.predicate OR r1.polarity <> r2.polarity)
RETURN DISTINCT r1.sentence_id AS sid_a, r2.sentence_id AS sid_b
"""


class Neo4jStore:
    def __init__(self):
        password = settings.neo4j_password
        if password is None:
            raise RuntimeError("NEO4J_PASSWORD not set in environment")
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, password.get_secret_value()),
        )
        self._driver.verify_connectivity()
        logger.info("Neo4j connected: {}", settings.neo4j_uri)
        self.ensure_schema()

    def close(self):
        self._driver.close()

    def _run(self, cypher: str, **params):
        with self._driver.session() as s:
            return list(s.run(cypher, **params))

    def ensure_schema(self):
        self._run("CREATE CONSTRAINT document_doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE")
        self._run("CREATE CONSTRAINT chunk_doc_sid IF NOT EXISTS FOR (c:Chunk) REQUIRE (c.doc_id, c.sentence_id) IS UNIQUE")
        self._run("CREATE CONSTRAINT entity_doc_name IF NOT EXISTS FOR (e:Entity) REQUIRE (e.doc_id, e.name) IS UNIQUE")
        self._run("CREATE CONSTRAINT run_run_id IF NOT EXISTS FOR (r:Run) REQUIRE r.run_id IS UNIQUE")
        self._run("CREATE INDEX chunk_doc_id IF NOT EXISTS FOR (c:Chunk) ON (c.doc_id)")
        self._run("CREATE INDEX relation_doc_id IF NOT EXISTS FOR ()-[r:RELATION]-() ON (r.doc_id)")
        self._run("CREATE INDEX relation_predicate IF NOT EXISTS FOR ()-[r:RELATION]-() ON (r.predicate)")
        self._run("CREATE INDEX run_doc_id IF NOT EXISTS FOR (r:Run) ON (r.doc_id)")
        self._run(
            f"CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS "
            f"FOR (c:Chunk) ON (c.embedding) "
            f"OPTIONS {{ indexConfig: {{ `vector.dimensions`: {settings.embed_dim}, `vector.similarity_function`: 'cosine' }} }}"
        )

    def doc_exists(self, doc_id: str) -> bool:
        rows = self._run("MATCH (d:Document {doc_id: $doc_id}) WHERE d.n_chunks > 0 RETURN d.doc_id AS id", doc_id=doc_id)
        return len(rows) > 0

    def get_doc_meta(self, doc_id: str) -> dict | None:
        rows = self._run(
            "MATCH (d:Document {doc_id: $doc_id}) "
            "RETURN d.doc_id AS doc_id, d.preview AS preview, d.n_chunks AS n_chunks, "
            "       d.n_triples AS n_triples, d.created_at AS created_at",
            doc_id=doc_id,
        )
        return dict(rows[0]) if rows else None

    def ensure_doc_stub(self, doc_id: str, text: str, preview: str):
        """Create a Document node with the full text but no chunks (used by naive method)."""
        self._run(
            "MERGE (d:Document {doc_id: $doc_id}) "
            "ON CREATE SET d.created_at = $created_at, d.n_chunks = 0, d.n_triples = 0 "
            "SET d.text = $text, d.preview = $preview",
            doc_id=doc_id,
            text=text,
            preview=preview,
            created_at=int(time.time()),
        )

    def ingest_document(self, doc_id: str, text: str, preview: str, chunks: list[dict]) -> dict:
        n_chunks = len(chunks)
        n_triples = sum(len(c["triples"]) for c in chunks)
        with self._driver.session() as s:
            s.run(
                INSERT_QUERY,
                doc_id=doc_id,
                text=text,
                preview=preview,
                n_chunks=n_chunks,
                n_triples=n_triples,
                created_at=int(time.time()),
                chunks=chunks,
            )
        logger.info("Ingested doc {} ({} chunks, {} triples)", doc_id, n_chunks, n_triples)
        return {"n_chunks": n_chunks, "n_triples": n_triples}

    def structural_pairs(self, doc_id: str) -> set[tuple[int, int]]:
        pairs: set[tuple[int, int]] = set()
        for cypher in (S_SR, S_SO):
            for r in self._run(cypher, doc_id=doc_id):
                a, b = sorted([r["sid_a"], r["sid_b"]])
                pairs.add((a, b))
        return pairs

    def get_chunks(self, doc_id: str) -> list[dict]:
        rows = self._run(
            "MATCH (c:Chunk {doc_id: $doc_id}) "
            "RETURN c.sentence_id AS sentence_id, c.source_text AS source_text, c.embedding AS embedding "
            "ORDER BY c.sentence_id",
            doc_id=doc_id,
        )
        return [dict(r) for r in rows]

    def save_run(
        self,
        run_id: str,
        doc_id: str,
        method: str,
        verifier_model: str,
        events_json: str,
        pair_count: int,
        total_elapsed: float,
    ):
        self._run(
            "MATCH (d:Document {doc_id: $doc_id}) "
            "CREATE (r:Run {"
            "  run_id: $run_id, doc_id: $doc_id, method: $method, verifier_model: $verifier_model, "
            "  events_json: $events_json, pair_count: $pair_count, "
            "  total_elapsed: $total_elapsed, created_at: $created_at"
            "}) "
            "CREATE (r)-[:EXECUTED_FOR]->(d)",
            run_id=run_id,
            doc_id=doc_id,
            method=method,
            verifier_model=verifier_model,
            events_json=events_json,
            pair_count=pair_count,
            total_elapsed=total_elapsed,
            created_at=int(time.time()),
        )
        logger.info("Saved run {} (doc={}, method={}, pairs={})", run_id, doc_id, method, pair_count)

    def list_runs(self) -> list[dict]:
        rows = self._run(
            "MATCH (r:Run)-[:EXECUTED_FOR]->(d:Document) "
            "RETURN r.run_id AS run_id, r.method AS method, r.verifier_model AS verifier_model, "
            "       r.pair_count AS pair_count, r.total_elapsed AS total_elapsed, "
            "       r.created_at AS created_at, d.doc_id AS doc_id, d.preview AS preview, "
            "       d.n_chunks AS n_chunks, d.n_triples AS n_triples "
            "ORDER BY r.created_at DESC"
        )
        return [dict(r) for r in rows]

    def get_run(self, run_id: str) -> dict | None:
        rows = self._run(
            "MATCH (r:Run {run_id: $run_id})-[:EXECUTED_FOR]->(d:Document) "
            "RETURN r.run_id AS run_id, r.method AS method, r.verifier_model AS verifier_model, "
            "       r.events_json AS events_json, r.pair_count AS pair_count, "
            "       r.total_elapsed AS total_elapsed, r.created_at AS created_at, "
            "       d.doc_id AS doc_id, d.text AS document_text, d.preview AS preview, "
            "       d.n_chunks AS n_chunks, d.n_triples AS n_triples",
            run_id=run_id,
        )
        return dict(rows[0]) if rows else None

    def delete_run(self, run_id: str):
        rows = self._run("MATCH (r:Run {run_id: $run_id}) RETURN r.doc_id AS doc_id", run_id=run_id)
        doc_id = rows[0]["doc_id"] if rows else None

        self._run("MATCH (r:Run {run_id: $run_id}) DETACH DELETE r", run_id=run_id)

        if doc_id:
            remaining = self._run("MATCH (r:Run {doc_id: $doc_id}) RETURN count(r) AS n", doc_id=doc_id)
            if remaining and remaining[0]["n"] == 0:
                self._run("MATCH (n:Chunk {doc_id: $doc_id}) DETACH DELETE n", doc_id=doc_id)
                self._run("MATCH (n:Entity {doc_id: $doc_id}) DETACH DELETE n", doc_id=doc_id)
                self._run("MATCH (d:Document {doc_id: $doc_id}) DETACH DELETE d", doc_id=doc_id)
                logger.info("Deleted run {} and orphaned doc {}", run_id, doc_id)
            else:
                logger.info("Deleted run {} (doc {} kept, still referenced by other runs)", run_id, doc_id)

    def clear_all(self):
        for label in ("Run", "Chunk", "Entity", "Document"):
            self._run(f"MATCH (n:{label}) DETACH DELETE n")
        logger.info("Cleared all runs and corpus")
