# Her

An anonymous fictional Persian companion with a Telegram audio archive and
durable channel publishing. Papilio owns the API and MySQL persistence;
papilio-tasks runs the Redis worker and scheduler; aiogram handles Telegram
long polling and delivery.

## Structure

- `api/her_api/modules/persona`: identity protection and initial fictional traits.
- `api/her_api/modules/ops`: database policies, durable updates and commands.
- `api/her_api/modules/library`: Telegram audio references and metadata.
- `api/her_api/modules/publishing`: evening plans and delivery records.
- `api/her_api/modules/content`: observed and explicitly imported channel context.
- `api/her_api/modules/ai`: bounded OpenRouter generation and usage accounting.
- `api/her_api/modules/conversations`: isolated history and authorized owner tools.
- `bots/her_bot`: Telegram adapter, menus and internal delivery gateway.
- `packages/contracts`: typed boundaries shared by both applications.

## Run

Requires Docker Compose. For development, use Python 3.13, MySQL 8.4 and Redis 8.
Framework sources and Python dependencies are pinned in the lock files.

1. Copy `.env.example` to a private `.env` and restrict its permissions.
2. Set the bot token, OpenRouter key, numeric owner/channel IDs, bootstrap model,
   a random service key of at least 32 characters and independent MySQL passwords.
   Hexadecimal passwords avoid URL escaping in the Compose database URL.
3. Supply SHA-256 fingerprints of protected identities in `HER_IDENTITY_HASHES`.
   Normalize with NFKC, HTML unescaping, case folding, Persian letter normalization
   and removal of format characters; hash joined word characters. Store only
   fingerprints. Never copy identifying source material into prompts or policies.
4. Add the bot as a channel administrator with posting permission. If configuring
   a discussion group, add the bot there as well. Start its private chat as owner.
5. Run `docker compose build`, then `docker compose up -d`.

The initialization service applies Alembic migrations before seeding missing
policies. Existing policies are preserved. Infrastructure remains in Compose and
environment variables; access, persona, model and publishing policies live in
MySQL. Publishing starts paused and group member chat starts disabled.

The API and bot gateway have no public port mappings. Run exactly one polling bot
and one scheduler. The worker uses native task discovery; no manual queue list is
maintained. Health checks verify API database/Redis access and bot readiness.

## Owner workflows

| Command | Behavior |
| --- | --- |
| `/start`, `/about`, `/back` | Home menu and navigation |
| `/status`, `/plan` | Private publishing status and persisted schedule |
| Upload Telegram **Audio** | Archive its reusable file reference; no audio download |
| `/tracks [PAGE]` | Paginated audio archive |
| `/tag ID calm night,quiet` | Mood and tag metadata |
| `/disable ID`, `/enable ID` | Control future use of an archived song |
| `/preview ID` | Private song preview |
| `/draft TOPIC` | Generate a public draft without publishing |
| `/publish TEXT`, `/play ID [CAPTION]` | Explicit channel publication |
| `/pause`, `/resume` | Persistently pause/resume automatic publishing |
| `/text_range MIN MAX` | Set the next evening's random text count range |
| `/group_on`, `/group_off` | Enable/disable addressed member conversations |
| `/profile [JSON]`, `/model [JSON]` | Read or replace typed database policies privately |
| `/channel_context` | Actual observed/imported coverage, including known gaps |
| `/import_channel` | Open a ten-minute private JSON import session |
| `/import_confirm TOKEN [map]` | Confirm a preview; `map` explicitly accepts another export ID |
| `/context_remove MESSAGE_ID` | Remove a context record, without deleting Telegram content |
| `/resolve JOB sent MESSAGE_ID`, `/resolve JOB skip` | Resolve an uncertain send by owner assertion |
| `/retry JOB`, `/retry JOB confirm` | Explicit retry after a temporary duplicate-risk confirmation |
| `/delete_confirm TOKEN` | Confirm deletion of a recorded own text post |
| `/forget` | Delete only the sender's conversation history in the current chat |

Owner authentication uses Telegram numeric sender IDs. Channel posts, anonymous
administrators and other bots cannot run owner commands. Private conversations
are owner-only; group conversations require the configured group, enabled member
chat and an alias/mention/reply. Owner greetings remain available while publishing
is paused or member chat is disabled. Administrative results are private.

The optional internal policy endpoint is `/internal/settings/{key}`. Read the
current revision, then PUT a typed `{ "revision": ..., "value": ... }` with the
internal Bearer service key. Concurrent changes require reloading the revision.
Never expose this endpoint to the public Internet.

## Publishing and recovery

New installations schedule daily text from 09:00 until 02:00 and music from
18:00 until 02:00 in `Asia/Tehran`. The database window policy owns the music
`start`, shared `end`, and optional earlier `text_start`; omitting `text_start`
preserves the legacy shared window. Three distinct songs and a uniformly sampled
number of text posts (one through five) receive persisted random timestamps
across their respective windows. Text count zero
is supported. Restarts, pauses and later policy changes preserve an existing plan.
An archive shortage blocks music scheduling and warns the owner once; independent
text scheduling continues.

Generation and delivery use separate worker tasks. Eligible planned posts and
music captions are generated ahead of their publication times, validated and
stored in MySQL. The scheduler selects only prepared, due jobs for delivery;
the sending worker never calls the language model. A stored text survives
restarts and Telegram retries. Pausing automatic publication also pauses
preparation of its remaining unprepared slots. Manual jobs remain independent.

Audio uses the same bot's Telegram file reference and one captioned `sendAudio`.
Daily text uses brief conversational preferences and observations. Music captions
use the track's recorded mood; editable per-mood fallback choices keep captions
varied during model outages without inventing a mood for an unclassified track.
Safe captions can repeat when the configured choices are exhausted.
Successful delivery requires an actual Telegram message ID. Rate limits retry
within bounded attempts and deadlines. Timeouts, ambiguous server errors and
interrupted sends become `delivery_unknown`; they are not retried automatically.
Expired automatic slots are not replayed into a later evening. Destination gates
serialize sends, and update/action uniqueness prevents ordinary replay effects.
Telegram has no general send idempotency key, so an explicitly confirmed retry of
an uncertain job can duplicate a message.

## Privacy and models

The persona is explicitly fictional. Identity fingerprints are checked before
persistence and public output. Private owner facts/history are excluded from
channel posts and tool-driven publication prompts. Each conversation is scoped
by chat and user; retained exchanges default to seven days. Channel context
defaults to ninety days, while delivery records retain their identities/status.

OpenRouter requests require zero-data-retention routing, deny provider data
collection and require supported parameters. Routing restrictions are never
relaxed after an error. Call budgets, model choice and token limits are editable
database policies. A provider or credit error produces a local safe fallback;
music sending can continue without generated captions. Provider routing settings
do not remove the need to protect the application's own database and backups.

Channel context includes only received updates, valid owner-forwarded channel
posts and confirmed text imports. It does not claim complete Telegram history or
knowledge of unseen deletions. Imports never execute paths or fetch embedded URLs.
No media downloader, browser scraper or arbitrary network/shell tool is included.

## Development and tests

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r api/requirements-dev.lock -r bots/requirements.lock
.venv/bin/pip install --no-deps -e packages/contracts -e api -e bots
.venv/bin/pip check
```

Set `PAPILIO_CONFIG` to the infrastructure sample and configure private environment
variables. `python -m her_api.apps.initialize` applies migrations and bootstrap.
Use the same API, worker, scheduler and bot entry points shown in Compose.

For integration tests, provide `HER_TEST_DATABASE_URL` with an isolated database
name beginning with `her_test`, plus an isolated `HER_TEST_REDIS_URL`. Fixtures
reset that test schema and use unique native queue namespaces. MySQL, Redis,
Alembic, HTTP API, scheduler, worker and aiogram execute on the tested path;
Telegram and OpenRouter HTTP responses are controlled external boundaries.
These tests do not prove live provider generation or production channel posting.

Run scoped pytest workflows, Ruff check/format and standard Pyright for changed
features. CI runs the complete suite and builds both production images.

Back up MySQL and private credentials before upgrading. Apply migrations before
starting updated applications. Preserve Redis persistence for queued work; durable
MySQL recovery also reconstructs eligible work after a queue interruption. Never
delete database volumes to apply an upgrade. The settings expansion migration
preserves existing values and intentionally refuses a destructive downgrade.

Private specification material, credentials and local operator artifacts are
excluded from Git and Docker contexts. The repository contains only application,
deployment and verification code.

## License

MIT; see [LICENSE](LICENSE).
