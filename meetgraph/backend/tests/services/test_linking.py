from app.services.linking import (
    normalize_person,
    normalize_text,
    similarity,
    build_timeline,
    LINK_THRESHOLD,
)


def _item(cid, person, text, meeting="m1", status="COMMITTED", created="2026-01-01T00:00:00"):
    return {
        "commitment_id": cid,
        "person": person,
        "commitment": text,
        "deadline": None,
        "status": status,
        "meeting_id": meeting,
        "meeting_title": meeting,
        "meeting_created_at": created,
        "evidence": {"speaker": person, "timestamp": 1.0, "text": text, "segment_id": f"s{cid}"},
    }


def test_normalize_person():
    assert normalize_person("  Rahul  ") == "rahul"
    assert normalize_person("RAHUL") == "rahul"
    assert normalize_person(None) == ""
    assert normalize_person(123) == ""


def test_similarity_identical():
    assert similarity("Prepare the budget report", "Prepare the budget report") == 1.0


def test_similarity_empty():
    assert similarity("", "something") == 0.0
    assert similarity(None, "something") == 0.0


def test_similarity_separates_related_from_unrelated():
    related = similarity("Prepare the budget report", "Prepare budget report for Q3")
    unrelated = similarity("Prepare the budget report", "Book flight tickets to Delhi")
    assert related >= LINK_THRESHOLD
    assert unrelated < LINK_THRESHOLD


def test_build_timeline_empty():
    assert build_timeline([]) == []


def test_build_timeline_links_same_action_across_meetings():
    items = [
        _item(1, "Rahul", "Prepare the budget report", meeting="m1", status="COMMITTED", created="2026-01-01T00:00:00"),
        _item(2, "Rahul", "Prepare budget report for Q3", meeting="m2", status="OPEN", created="2026-01-02T00:00:00"),
        _item(3, "Rahul", "Prepare the budget report", meeting="m3", status="COMPLETED", created="2026-01-03T00:00:00"),
    ]
    threads = build_timeline(items)
    assert len(threads) == 1
    thread = threads[0]
    assert thread["person"] == "Rahul"
    assert thread["meeting_count"] == 3
    assert [i["commitment_id"] for i in thread["items"]] == [1, 2, 3]
    assert [i["status"] for i in thread["items"]] == ["COMMITTED", "OPEN", "COMPLETED"]
    # Evidence preserved on every item
    assert all(i["evidence"]["text"] for i in thread["items"])


def test_build_timeline_separates_people_and_actions():
    items = [
        _item(1, "Rahul", "Prepare the budget report", meeting="m1"),
        _item(2, "rahul", "Book flight tickets to Delhi", meeting="m2"),
        _item(3, "Priya", "Prepare the budget report", meeting="m2"),
    ]
    threads = build_timeline(items)
    assert len(threads) == 3


def test_build_timeline_person_case_insensitive_link():
    items = [
        _item(1, "Rahul", "Prepare the budget report", meeting="m1"),
        _item(2, "RAHUL", "Prepare the budget report", meeting="m2"),
    ]
    threads = build_timeline(items)
    assert len(threads) == 1
