"""
Browser front end for condensed combat -- mirrors AGGRO's web.py pattern at
a fraction of the scale: single module-level state global (local single-
player tool, no sessions needed), plain server-rendered Jinja2 with
full-page-reload form buttons (no JS framework, no fetch/AJAX). Calls
playtest_engine directly, same engine playtest_cli.py uses.

Run:
    python playtest_web.py
    python playtest_web.py --port 8080
"""
from __future__ import annotations

import argparse
import json

from flask import Flask, redirect, render_template, request, url_for

import condensed_trip as T
import playtest_engine as E

app = Flask(__name__, template_folder="playtest_templates")

_state: E.PullState = None


@app.route("/")
def index():
    return render_template("setup.html", classes=list(E.CARD_SOURCE.keys()), mobs=list(T.MOBS.keys()))


@app.route("/start", methods=["POST"])
def start():
    global _state
    class_name = request.form.get("class_name")
    mob_name = request.form.get("mob_name")
    _state = E.new_pull(class_name, mob_name)
    return redirect(url_for("play"))


@app.route("/play")
def play():
    if _state is None:
        return redirect(url_for("index"))
    actions = E.legal_actions(_state)
    grouped = {}
    for i, a in enumerate(actions):
        grouped.setdefault(a["card"], []).append((i, a))
    # Pre-serialize each card's legal [idx, action] pairs so the template
    # only ever does a plain string interpolation into data-actions --
    # trying to filter/reshape tuples into JSON inside Jinja itself is
    # fragile and hard to read; do it in Python where it's just a list comp.
    legal_actions_json = {
        card_name: json.dumps([[i, a] for i, a in entries if a["legal"]])
        for card_name, entries in grouped.items()
    }
    return render_template(
        "game.html", state=_state, grouped=grouped, legal_actions_json=legal_actions_json,
        pattern=list(enumerate(_state.mob_pattern)),
    )


@app.route("/action", methods=["POST"])
def action():
    global _state
    if _state is None:
        return redirect(url_for("index"))
    idx = int(request.form.get("action_idx", -1))
    actions = E.legal_actions(_state)
    if 0 <= idx < len(actions) and actions[idx]["legal"]:
        chosen = actions[idx]
        _state = E.apply_action(_state, chosen["card"], chosen["stance"])
    if _state.outcome is not None:
        return redirect(url_for("result"))
    return redirect(url_for("play"))


@app.route("/result")
def result():
    if _state is None or _state.outcome is None:
        return redirect(url_for("index"))
    reveal = E.best_line_reveal(_state)
    return render_template("result.html", state=_state, reveal=reveal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5151)
    parser.add_argument("--localhost", action="store_true", help="Bind to 127.0.0.1 only")
    args = parser.parse_args()
    host = "127.0.0.1" if args.localhost else "0.0.0.0"
    print(f"\n  QUEST condensed combat playtest\n  Open http://localhost:{args.port} in your browser\n")
    app.run(host=host, debug=False, port=args.port)


if __name__ == "__main__":
    main()
