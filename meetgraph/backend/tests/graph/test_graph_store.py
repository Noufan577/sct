from app.graph.store import build_graph


def _item(cid, person, text, meeting="m1", title=None, status="COMMITTED"):
    return {
        "commitment_id": cid,
        "person": person,
        "commitment": text,
        "deadline": None,
        "status": status,
        "meeting_id": meeting,
        "meeting_title": title or f"Title {meeting}",
        "meeting_created_at": f"2026-01-0{cid}T00:00:00",
        "evidence": {"speaker": person, "timestamp": 1.0, "text": text, "segment_id": f"s{cid}"},
    }


def _items():
    return [
        _item(1, "Rahul", "Prepare the budget report", meeting="m1", status="COMMITTED"),
        _item(2, "Rahul", "Prepare budget report for Q3", meeting="m2", status="COMPLETED"),
        _item(3, "Priya", "Book flight tickets", meeting="m1", status="OPEN"),
    ]


def test_graph_nodes_and_edges():
    g = build_graph(_items())
    by_id = {n["id"]: n for n in g["nodes"]}
    # 2 people + 2 meetings + 3 commitments
    assert len(g["nodes"]) == 7
    assert by_id["p:Rahul"]["type"] == "person"
    assert by_id["m:m1"]["type"] == "meeting"
    assert by_id["c:1"]["status"] == "COMMITTED"
    labels = [e["label"] for e in g["edges"]]
    assert labels.count("made") == 3
    assert labels.count("in") == 3
    # Rahul's two commitments link across meetings
    assert {"source": "c:1", "target": "c:2", "label": "same thread"} in g["edges"]


def test_graph_person_filter():
    g = build_graph(_items(), person="rahul")
    ids = {n["id"] for n in g["nodes"]}
    assert ids == {"p:Rahul", "m:m1", "m:m2", "c:1", "c:2"}
    assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])


def test_graph_empty():
    assert build_graph([]) == {"nodes": [], "edges": []}
    assert build_graph(_items(), person="Nobody") == {"nodes": [], "edges": []}


def test_graph_apostrophe_text():
    items = [
        _item(1, "Rahul", "I'll have it ready by Friday", meeting="m1", status="COMMITTED"),
    ]
    g = build_graph(items)
    assert len(g["nodes"]) == 3
    assert g["nodes"] and any(n["label"] == "I'll have it ready by Friday" for n in g["nodes"])
