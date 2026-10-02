"""Meeting relation graph on LadybugDB (embedded property graph).

SQLite stays the system of record. This module builds an IN-MEMORY
Ladybug graph per request from stored commitments plus timeline
threads, then answers with real Cypher — so relations (who made
what, what was said where, what links across meetings) are graph
queries, not hand-rolled joins.

Schema:
  (Person)-[:MADE]->(Commitment)-[:IN_MEETING]->(Meeting)
  (Commitment)-[:LINKED]->(Commitment)   same thread, chronological
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.linking import build_timeline, normalize_person

logger = logging.getLogger(__name__)


class LadybugGraph:
    def __init__(self):
        import ladybug as lb

        self._db = lb.Database(":memory:")
        self._conn = lb.Connection(self._db)
        self._conn.execute("CREATE NODE TABLE Person(name STRING, PRIMARY KEY(name))")
        self._conn.execute(
            "CREATE NODE TABLE Meeting(mid STRING, title STRING, PRIMARY KEY(mid))"
        )
        self._conn.execute(
            "CREATE NODE TABLE Commitment(cid INT64, text STRING, status STRING, PRIMARY KEY(cid))"
        )
        self._conn.execute("CREATE REL TABLE MADE(FROM Person TO Commitment)")
        self._conn.execute("CREATE REL TABLE IN_MEETING(FROM Commitment TO Meeting)")
        self._conn.execute("CREATE REL TABLE LINKED(FROM Commitment TO Commitment)")

    def load(self, items: List[Dict[str, Any]], threads: List[Dict[str, Any]]) -> None:
        people: Dict[str, str] = {}
        for item in items:
            key = normalize_person(item.get("person"))
            if key and key not in people:
                people[key] = item.get("person") or "Unknown"
        for display in people.values():
            self._conn.execute("CREATE (p:Person {name: $name})", {"name": display})

        seen_meetings = set()
        for item in items:
            mid = item.get("meeting_id")
            if mid in seen_meetings:
                continue
            seen_meetings.add(mid)
            self._conn.execute(
                "CREATE (m:Meeting {mid: $mid, title: $title})",
                {"mid": mid, "title": item.get("meeting_title") or mid},
            )
        for item in items:
            cid = int(item.get("commitment_id"))
            self._conn.execute(
                "CREATE (c:Commitment {cid: $cid, text: $text, status: $status})",
                {
                    "cid": cid,
                    "text": item.get("commitment") or "",
                    "status": item.get("status") or "",
                },
            )
            person = people.get(normalize_person(item.get("person")), "Unknown")
            self._conn.execute(
                "MATCH (p:Person), (c:Commitment) "
                "WHERE p.name = $name AND c.cid = $cid "
                "CREATE (p)-[:MADE]->(c)",
                {"name": person, "cid": cid},
            )
            self._conn.execute(
                "MATCH (c:Commitment), (m:Meeting) "
                "WHERE c.cid = $cid AND m.mid = $mid "
                "CREATE (c)-[:IN_MEETING]->(m)",
                {"cid": cid, "mid": item.get("meeting_id")},
            )
        for thread in threads:
            ids = [i.get("commitment_id") for i in thread.get("items", [])]
            for a, b in zip(ids, ids[1:]):
                self._conn.execute(
                    "MATCH (x:Commitment), (y:Commitment) "
                    "WHERE x.cid = $a AND y.cid = $b "
                    "CREATE (x)-[:LINKED]->(y)",
                    {"a": int(a), "b": int(b)},
                )

    def fetch(self, person: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        if person:
            rows = self._conn.execute(
                "MATCH (p:Person)-[:MADE]->(c:Commitment)-[:IN_MEETING]->(m:Meeting) "
                "WHERE p.name = $name "
                "RETURN p.name, c.cid, c.text, c.status, m.mid, m.title",
                {"name": person},
            ).rows_as_dict()
        else:
            rows = self._conn.execute(
                "MATCH (p:Person)-[:MADE]->(c:Commitment)-[:IN_MEETING]->(m:Meeting) "
                "RETURN p.name, c.cid, c.text, c.status, m.mid, m.title"
            ).rows_as_dict()
        links = self._conn.execute(
            "MATCH (a:Commitment)-[:LINKED]->(b:Commitment) RETURN a.cid, b.cid"
        ).rows_as_dict()

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        seen_cids = set()
        for r in rows:
            pid, cid, mid = f"p:{r['p.name']}", f"c:{r['c.cid']}", f"m:{r['m.mid']}"
            nodes.setdefault(pid, {"id": pid, "type": "person", "label": r["p.name"]})
            nodes.setdefault(
                mid, {"id": mid, "type": "meeting", "label": r["m.title"] or r["m.mid"]}
            )
            nodes[cid] = {
                "id": cid,
                "type": "commitment",
                "label": r["c.text"],
                "status": r["c.status"],
            }
            seen_cids.add(r["c.cid"])
            edges.append({"source": pid, "target": cid, "label": "made"})
            edges.append({"source": cid, "target": mid, "label": "in"})
        for link in links:
            if link["a.cid"] in seen_cids and link["b.cid"] in seen_cids:
                edges.append(
                    {
                        "source": f"c:{link['a.cid']}",
                        "target": f"c:{link['b.cid']}",
                        "label": "same thread",
                    }
                )
        return {"nodes": list(nodes.values()), "edges": edges}


def build_graph(
    items: List[Dict[str, Any]], person: Optional[str] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Build the relation graph for items (optionally one person)."""
    if person:
        wanted = normalize_person(person)
        items = [i for i in items if normalize_person(i.get("person")) == wanted]
    if not items:
        return {"nodes": [], "edges": []}
    threads = build_timeline(items)
    graph = LadybugGraph()
    graph.load(items, threads)
    # Filter Cypher-side by display name resolved from the filtered items.
    display = items[0].get("person") if person else None
    return graph.fetch(display)
