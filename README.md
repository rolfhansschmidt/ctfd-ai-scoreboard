# CTFd AI Scoreboard

A CTFd plugin that lets each team declare its AI usage and integrates the
declaration with CTFd's native scoreboard brackets. The standard scoreboard
template, graph, and JavaScript remain unchanged.

## Categories

| Team declaration | Scoreboard bracket |
| --- | --- |
| AI chatbot | AI chatbot + AI agent |
| AI agent | AI chatbot + AI agent |
| No AI | No AI |
| Fully Automized | Fully Automized |

The required `ai_usage_state` custom team field is selectable only during team
creation. Teams cannot change it afterward, including through the API.
Administrators can still correct a declaration through CTFd's admin API.
Existing installations automatically mark this field non-editable when the
plugin loads. The existing scoreboard filter bar
is made sticky for long leaderboards. `/ai-scoreboards` redirects to `/scoreboard`.

## Installation

Tested with CTFd 3.8.9 in team mode. Other versions have not been verified.
No dependencies beyond CTFd's installed requirements are needed.

1. Back up your CTFd database.
2. Copy the `ai_usage_scoreboards` directory into `CTFd/plugins/`.
3. Restart CTFd using your deployment's normal service/container workflow.
4. Use team mode and create a team with an AI usage declaration.

The plugin provisions its team custom field and the three native brackets
when loaded. It reuses existing objects with the same names.

For Docker, mount the plugin directory at
`/opt/CTFd/CTFd/plugins/ai_usage_scoreboards:ro`. Ensure the container user
can read the files and traverse the directory.

## Existing events

Install before registration opens where possible. Existing teams need a valid
`ai_usage_state` declaration. Loading this plugin does not automatically infer
declarations or migrate every existing team. An administrator must set any
missing declaration through the admin API, which synchronizes its native bracket.

This plugin uses team brackets for AI categories. An event that already uses
brackets for another classification needs a separate integration design.

## Integration and security

- Uses native CTFd team custom fields and native scoreboard brackets.
- Enhances the custom text field with a dropdown using its database ID.
- Validates values server-side, including API requests and duplicate declarations.
- Derives the creation bracket from the declaration on the server.
- Synchronizes ORM writes and brackets in the same transaction.
- Leaves CTFd authentication, captain permissions, and CSRF checks in place.
- Invalidates scoreboard and team caches after successful request writes.

JavaScript enhancement follows CTFd's documented approach:
https://docs.ctfd.io/tutorials/users/adding-custom-field-dropdowns/

Targeted checks performed on the original deployment included captain updates,
non-captain rejection, CSRF rejection, malformed payloads, duplicate values,
invalid ORM values, rollback behavior, and creation with a forged bracket.
These checks are not an independent penetration test or a compatibility
guarantee for other CTFd versions.

The registration-only regression test is in `tests/test_registration_only.py`.
It creates and removes temporary users and teams in a configured CTFd
environment. It covers all four registration values, absence of the field in
team settings, rejection of captain API declaration writes, preservation of
the declaration and bracket, and unrelated profile edits. Run it from the
repository root with your CTFd Compose file:

```sh
docker compose -f /path/to/docker-compose.yml exec -T -e PYTHONPATH=/opt/CTFd ctfd python - < tests/test_registration_only.py
```

Bulk SQL updates bypass SQLAlchemy ORM listeners. Maintenance scripts must
preserve the declaration/bracket relationship and invalidate caches themselves.
Direct invalid ORM values raise `ValueError`; request validation handles the
normal HTTP write paths before persistence.

## Repository contents

Only the active plugin source is included. Deployment configuration,
credentials, event data, seed scripts, and the superseded standalone
scoreboard template are not included.
