# BYOK planner wire contract

Tempera Air does not bundle an AI provider. Users register their own
planner endpoint (with their own API key) and the CLI asks it for an
action plan. The plan is saved as a guarded macro; it is never executed
directly and must pass the same replay gates as any imported macro.

The machine contract is committed at
`contracts/planner-wire.schema.json` (schema version 1).

## Registering a planner

```
android-sim planner add --name my-planner \
  --endpoint https://planner.example.com/plan \
  --api-key-env MY_PLANNER_KEY \
  --model my-model
```

- The endpoint must use HTTPS. Plain HTTP is accepted only on loopback
  hosts (`127.0.0.1`, `localhost`, `::1`) for local models.
- The API key is read from the named environment variable at call time
  and sent as `Authorization: Bearer <key>`. It is never written to disk.

## Request

`POST` to the registered endpoint with `Content-Type: application/json`:

```json
{
  "schema_version": 1,
  "goal": "open settings and enable airplane mode",
  "model": "my-model",
  "allowed_actions": ["back", "home", "swipe", "tap", "type", "wait"],
  "action_arguments": {
    "tap": {"x": "integer", "y": "integer"},
    "type": {"text": "string"},
    "swipe": {"x1": "integer", "y1": "integer", "x2": "integer", "y2": "integer", "duration_ms": "optional integer, default 300"},
    "back": {},
    "home": {},
    "wait": {"seconds": "optional number between 0 and 60, default 1"}
  }
}
```

## Response

```json
{
  "schema_version": 1,
  "steps": [
    {"action": "tap", "arguments": {"x": 540, "y": 1200}, "description": "open settings"},
    {"action": "wait", "arguments": {"seconds": 1}}
  ]
}
```

Rules:

- `schema_version` must be `1`.
- `steps` must contain 1-10000 entries.
- Every `action` must be one of `allowed_actions`; anything else is
  rejected and nothing is saved.
- `arguments` must be a JSON object; unknown actions or malformed steps
  abort the plan before it is stored.
- Responses larger than 1 MiB are rejected.

## Generating and replaying a plan

```
android-sim planner plan my-planner --goal "open settings" --save-as open-settings
android-sim macro run open-settings            # normal replay gates apply
android-sim macro run open-settings --yes      # required when a step is sensitive
```

The `planner plan` result reports:

- `requires_confirmation`: any step matched the sensitive-term list.
- `contains_typed_text`: any step types text, which is stored verbatim in
  the macro file.

Refusing to overwrite an existing macro is the default; pass `--force`
to replace it.
