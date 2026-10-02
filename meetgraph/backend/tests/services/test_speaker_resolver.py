from app.services.speaker_resolver import resolve_speakers


def _seg(id, speaker, text):
    return {"id": id, "speaker": speaker, "text": text}


def test_self_introduction_maps_label():
    segments = [
        _seg("s1", "Speaker 1", "Hi everyone, I'm Rahul."),
        _seg("s2", "Speaker 2", "Good morning."),
    ]
    out = resolve_speakers(segments)
    assert out["Speaker 1"]["person"] == "Rahul"
    assert out["Speaker 1"]["method"] == "self_intro"
    assert out["Speaker 1"]["evidence_segment_id"] == "s1"


def test_addressed_by_name_low_confidence():
    segments = [
        _seg("s1", "Speaker A", "Thanks, Arjun, for the update."),
        _seg("s2", "Speaker B", "Done."),
    ]
    out = resolve_speakers(segments)
    # Speaker B is addressed; maps to Arjun with low confidence.
    assert out["Speaker B"]["person"] == "Arjun"
    assert out["Speaker B"]["confidence"] == 0.5
    assert out["Speaker B"]["method"] == "addressed_by_name"


def test_unresolved_keeps_label():
    segments = [_seg("s1", "Speaker 9", "Hello there.")]
    out = resolve_speakers(segments)
    assert out["Speaker 9"]["person"] == "Speaker 9"
    assert out["Speaker 9"]["method"] == "unresolved"
    assert out["Speaker 9"]["confidence"] == 0.0


def test_confirmed_reuse_wins():
    segments = [_seg("s1", "Speaker 1", "I'll take that task.")]
    out = resolve_speakers(segments, prior_confirmed={"Speaker 1": "Meera"})
    assert out["Speaker 1"]["person"] == "Meera"
    assert out["Speaker 1"]["method"] == "confirmed_reuse"


def test_greetings_not_treated_as_names():
    segments = [_seg("s1", "Speaker 1", "Sure, sir. You're welcome.")]
    out = resolve_speakers(segments)
    assert out["Speaker 1"]["method"] == "unresolved"
