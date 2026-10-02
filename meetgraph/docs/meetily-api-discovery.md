# Meetily API Discovery

## Meetily environment
Meetily version: 1.11.0 (OpenAPI 3.1.0)
Agent API: REACHABLE
Base URL: http://127.0.0.1:8420
Reachable: YES

## Authentication
Authentication: `Authorization: Bearer <token>`
Required scope: Read access (implied, no specific scopes documented in OpenAPI config)
Credential available: YES (Configured in `.env`)

## OpenAPI
OpenAPI available: YES
OpenAPI version: 3.1.0
Endpoint: http://127.0.0.1:8420/openapi.json

## Relevant endpoints
| Purpose | Method | Path | Scope |
|---|---|---|---|
| List meetings | GET | `/v1/meetings` | Token |
| Get meeting | GET | `/v1/meetings/{id}` | Token |
| Get transcript | GET | `/v1/meetings/{id}/transcript` | Token |
| Get summary | GET | `/v1/meetings/{id}/summary` | Token |

## Transcript schema
The `TranscriptSegmentDto` defines the following fields:
- `id` (string)
- `speaker` (string, optional)
- `text` (string)
- `timestamp` (string)
- `duration` (double, optional)
- `audio_start_time` (double, optional)
- `audio_end_time` (double, optional)
- `assigned_meeting_speaker_id` (int64, optional)
- `detected_meeting_speaker_id` (int64, optional)
- `words` (array, optional)

## Real Transcript Test
Meeting retrieved: YES (1 meeting found: 'first')
Transcript retrieved: YES
Number of segments: 245

## Files Created
- `meetgraph/scripts/analyze_openapi.py`
- `meetgraph/data/meetily/openapi.json`
- `meetgraph/docs/meetily-api-discovery.md`
- `meetgraph/backend/tests/fixtures/meetily/transcript_sample.json`

## Findings
- The Meetily Gateway API (v1.11.0) successfully responds to our Bearer token!
- The API uses the `/v1/` path prefix (not `/api/v1/`).
- The transcript segments contain both absolute `timestamp` values and relative `audio_start_time`/`audio_end_time`.
- `speaker` identification is available (as string and ID).
- A real transcript was successfully fetched and a sanitized fixture with 245 segments was saved to `backend/tests/fixtures/meetily/transcript_sample.json`.
