"""Integration regression test; run inside a configured CTFd 3.8.9 environment.

Creates temporary users and teams and removes them in finally blocks.
Run: docker compose exec -T -e PYTHONPATH=/opt/CTFd ctfd python - < tests/test_registration_only.py
"""
import secrets
import unittest

from flask import session

from CTFd import create_app
from CTFd.cache import cache
from CTFd.models import TeamFieldEntries, TeamFields, Teams, Users, db
from CTFd.utils.security.auth import login_user


class RegistrationOnlyTest(unittest.TestCase):
    def test_registration_and_locked_updates(self):
        app = create_app()
        with app.app_context():
            field = TeamFields.query.filter_by(name="ai_usage_state").one()
            self.assertFalse(field.editable)
            field_id = field.id
            before = Teams.query.count()
            for state in ("AI chatbot", "AI agent", "No AI", "Fully Automized"):
                name = "usage-test-" + secrets.token_hex(8)
                user = Users(name=name, email=name + "@example.test",
                             password=secrets.token_urlsafe(32))
                db.session.add(user)
                db.session.commit()
                user_id = user.id
                client = app.test_client()
                with app.test_request_context():
                    login_user(user)
                    auth = dict(session)
                with client.session_transaction() as current:
                    current.update(auth)
                headers = {"CSRF-Token": auth["nonce"]}
                try:
                    registration = client.get("/teams/new")
                    self.assertIn(f'name="fields[{field_id}]"', registration.get_data(as_text=True))
                    response = client.post("/teams/new", data={
                        "name": name, "password": secrets.token_urlsafe(32),
                        "nonce": auth["nonce"], f"fields[{field_id}]": state,
                    })
                    self.assertEqual(response.status_code, 302)
                    team = Teams.query.filter_by(name=name).one()
                    team_id = team.id
                    bracket_id = team.bracket_id
                    self.assertNotIn(f'name="fields[{field_id}]"',
                                     client.get("/team").get_data(as_text=True))
                    # A captain cannot change or resubmit the declaration,
                    # including an alternate field-id representation.
                    for value, fid in (("No AI", field_id), (state, str(field_id))):
                        response = client.patch("/api/v1/teams/me", headers=headers,
                                                json={"fields": [{"field_id": fid, "value": value}]})
                        self.assertEqual(response.status_code, 403)
                    response = client.patch("/api/v1/teams/me", headers=headers,
                                            json={"affiliation": "Regression test"})
                    self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
                    db.session.expire_all()
                    self.assertEqual(Teams.query.get(team_id).bracket_id, bracket_id)
                    self.assertEqual(TeamFieldEntries.query.filter_by(
                        team_id=team_id, field_id=field_id).one().value, state)
                    # Native CTFd authorization must also reject direct team-ID updates.
                    response = client.patch(f"/api/v1/teams/{team_id}", headers=headers,
                                            json={"bracket_id": bracket_id})
                    self.assertEqual(response.status_code, 403)
                finally:
                    db.session.rollback()
                    user = Users.query.get(user_id)
                    user.team_id = None
                    db.session.commit()
                    team = Teams.query.filter_by(name=name).first()
                    if team:
                        db.session.delete(team)
                        db.session.commit()
                    db.session.delete(user)
                    db.session.commit()
                    cache.clear()
            self.assertEqual(Teams.query.count(), before)


if __name__ == "__main__":
    unittest.main()
