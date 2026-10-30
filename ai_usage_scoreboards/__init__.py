"""CTFd 3.8.x team declarations and native scoreboard brackets."""
import json
from pathlib import Path

from flask import Blueprint, Response, abort, redirect, request, url_for
from sqlalchemy import event
from sqlalchemy.orm import Session

from CTFd.cache import clear_standings, clear_team_session
from CTFd.models import Brackets, TeamFieldEntries, TeamFields, Teams, db
from CTFd.plugins import register_plugin_script, register_plugin_stylesheet

FIELD = "ai_usage_state"
STATES = {
    "AI chatbot": "AI chatbot + AI agent",
    "AI agent": "AI chatbot + AI agent",
    "No AI": "No AI",
    "Fully Automized": "Fully Automized",
}
bp = Blueprint("ai_usage_scoreboards", __name__, static_folder="assets",
               static_url_path="/plugins/ai_usage_scoreboards/assets")


def configuration():
    field = TeamFields.query.filter_by(name=FIELD).one()
    brackets = Brackets.query.filter(
        Brackets.type == "teams", Brackets.name.in_(set(STATES.values()))
    ).all()
    return field.id, {b.name: b.id for b in brackets}


def enforce_usage(session, flush_context, instances):
    """Keep declaration and native bracket consistent in the same transaction."""
    changed = list(session.new) + list(session.dirty)
    if not any(isinstance(o, (Teams, TeamFieldEntries)) for o in changed):
        return
    field_id, brackets = configuration()
    teams = {o for o in changed if isinstance(o, Teams)}
    declarations = {}
    for entry in changed:
        if isinstance(entry, TeamFieldEntries) and entry.field_id == field_id:
            if not isinstance(entry.value, str) or entry.value not in STATES:
                raise ValueError("Invalid AI usage state")
            team = entry.team or session.query(Teams).get(entry.team_id)
            if team is not None:
                teams.add(team)
                declarations[team] = entry.value
    for team in teams:
        entries = [e for e in team.field_entries
                   if e.field_id == field_id and e not in session.deleted]
        if len(entries) > 1:
            raise ValueError("Duplicate AI usage declaration")
        value = declarations.get(team, entries[0].value if entries else None)
        if value is not None:
            if not isinstance(value, str) or value not in STATES:
                raise ValueError("Invalid AI usage state")
            team.bracket_id = brackets[STATES[value]]
            session.info.setdefault("ai_usage_changed", set()).add(team.id)


@bp.route("/ai-scoreboards")
def legacy_scoreboards():
    return redirect(url_for("scoreboard.listing"))


@bp.route("/plugins/ai_usage_scoreboards/registration.js")
def registration_script():
    field_id, brackets = configuration()
    config = {"field": field_id, "states": {
        state: brackets[name] for state, name in STATES.items()
    }}
    source = Path(__file__).with_name("assets").joinpath("register.js").read_text()
    return Response("const aiUsageConfig = " + json.dumps(config) + ";\n" + source,
                    mimetype="application/javascript",
                    headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"})


def load(app):
    # Existing field/brackets are reused. No public request provisions data.
    if TeamFields.query.filter_by(name=FIELD).first() is None:
        db.session.add(TeamFields(name=FIELD, field_type="text", required=True,
                                  public=True, editable=True,
                                  description="Select how your team uses AI"))
    for name in dict.fromkeys(STATES.values()):
        if Brackets.query.filter_by(type="teams", name=name).first() is None:
            db.session.add(Brackets(type="teams", name=name,
                                   description="AI usage category"))
    db.session.commit()
    app.register_blueprint(bp)
    register_plugin_script("/plugins/ai_usage_scoreboards/registration.js")
    register_plugin_stylesheet("/plugins/ai_usage_scoreboards/assets/scoreboard.css")
    if not event.contains(Session, "before_flush", enforce_usage):
        event.listen(Session, "before_flush", enforce_usage)

    @app.before_request
    def validate_payload():
        creation = request.endpoint == "teams.new" and request.method == "POST"
        api_write = (request.path.rstrip("/") == "/api/v1/teams" or
                     request.path.startswith("/api/v1/teams/")) and request.method in ("POST", "PATCH")
        if not (creation or api_write):
            return
        field_id, brackets = configuration()
        if creation:
            values = request.form.getlist(f"fields[{field_id}]")
        else:
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                abort(400, description="Expected a JSON object")
            entries = payload.get("fields", [])
            if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
                abort(400, description="Expected custom field objects")
            values = [e.get("value") for e in entries
                      if str(e.get("field_id")) == str(field_id)]
        if len(values) > 1 or any(not isinstance(v, str) or v not in STATES for v in values):
            abort(400, description="Select exactly one valid AI usage state")
        api_creation = request.path.rstrip("/") == "/api/v1/teams" and request.method == "POST"
        if (creation or api_creation) and not values:
            abort(400, description="AI usage state is required")
        if creation:
            form = request.form.copy()
            form["bracket_id"] = str(brackets[STATES[values[0]]])
            request.form = form

    @app.after_request
    def invalidate_caches(response):
        changed = db.session.info.pop("ai_usage_changed", set())
        if changed and response.status_code < 400:
            clear_standings()
            for team_id in changed:
                if team_id:
                    clear_team_session(team_id=team_id)
        return response
