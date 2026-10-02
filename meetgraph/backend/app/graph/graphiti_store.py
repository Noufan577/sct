"""Experimental Graphiti integration for MeetGraph.

Requires:
- pip install graphiti-core
- A running Neo4j instance (e.g., via Docker: `docker run -p 7687:7687 -p 7474:7474 -e NEO4J_AUTH=none neo4j`)
- OPENAI_API_KEY (Graphiti relies heavily on LLMs for embedding and entity extraction)
"""

import os
import asyncio
import logging
from typing import List, Dict, Any

from graphiti_core import Graphiti
from graphiti_core.nodes import EntityNode
from graphiti_core.edges import Edge

logger = logging.getLogger(__name__)

class GraphitiStore:
    def __init__(self):
        # Graphiti picks up NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD from env
        # as well as OPENAI_API_KEY
        self.client = Graphiti()
        
    async def ingest_meeting(self, meeting_id: str, title: str, commitments: List[Dict[str, Any]]):
        """Ingest a meeting's commitments into the temporal knowledge graph."""
        
        # 1. Create/Get the Meeting Node
        # Graphiti automatically handles timestamping and deduplication
        meeting_node = await self.client.add_node(
            name=title,
            labels=["Meeting"],
            properties={"meeting_id": meeting_id}
        )
        
        for item in commitments:
            person_name = item.get("person") or "Unknown"
            text = item.get("commitment") or ""
            status = item.get("status") or "OPEN"
            
            # 2. Create/Get the Person Node
            person_node = await self.client.add_node(
                name=person_name,
                labels=["Person"]
            )
            
            # 3. Create the Commitment Node
            commitment_node = await self.client.add_node(
                name=f"Task: {text[:30]}...",
                labels=["Commitment"],
                properties={
                    "full_text": text,
                    "status": status,
                    "original_id": item.get("commitment_id")
                }
            )
            
            # 4. Create Edges
            await self.client.add_edge(
                source_node_id=person_node.id,
                target_node_id=commitment_node.id,
                name="MADE",
                fact=f"{person_name} committed to: {text}"
            )
            
            await self.client.add_edge(
                source_node_id=commitment_node.id,
                target_node_id=meeting_node.id,
                name="IN_MEETING",
                fact=f"This commitment was made in meeting {title}"
            )

    async def query_person_commitments(self, person_name: str) -> List[Dict[str, Any]]:
        """Retrieve the timeline of commitments for a person using Graphiti's hybrid search."""
        # Graphiti allows us to query the graph both semantically and structurally.
        results = await self.client.search(
            query=f"What did {person_name} commit to?",
            limit=50
        )
        
        # Format results for the frontend timeline
        timeline = []
        for node in results.nodes:
            if "Commitment" in node.labels:
                timeline.append({
                    "commitment": node.properties.get("full_text"),
                    "status": node.properties.get("status"),
                    "person": person_name
                })
        return timeline
