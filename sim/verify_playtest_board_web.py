"""
Smoke test for playtest_board_web.py -- drives real Flask requests (app.test_client()) through
full sessions across all 9 classes, scripting a "dumb but always-legal" stand-in player, same
spirit as verify_playtest_board_cli.py's approach for the terminal version.

Reads playtest_board_web._S directly to decide what to submit next (which page/phase is
current, what the legal actions are) rather than scraping rendered HTML -- same "call the real
function, don't parse text" discipline the rest of this project's diagnostics already follow.
Safe because this is a single in-process global-state app (no per-session isolation to work
around), exactly the property that makes the whole "no threads, no sessions" architecture work.

Not a balance check -- exists purely to catch plumbing bugs (wrong form field names, wrong
dict keys, an unhandled phase) before a real human sits down with a browser.
"""
import random

import board_engine as BE
import macro_sim as M
import playtest_board_web as PW


def _pick_travel_action(rng):
    hero = PW._S["board"].heroes[0]
    actions = BE.get_travel_actions(hero, PW._S["board"], PW._S["rng"])
    return rng.randrange(len(actions))


def _submit_combat_plan(client, rng, max_attempts=20):
    """A submitted ordering can be legitimately rejected (e.g. Warrior's Execute picked before
    the mob is low enough) -- that's real, correct validation (see playtest_board_web's own
    _validate_sequence), not a bug, so this retries with a fresh random ordering the same way a
    real human would just pick again, rather than treating one rejection as a failure."""
    class_name = PW._S["class_names"][0]
    for _attempt in range(max_attempts):
        hand = PW._S["pending_hand"]
        options = PW._hand_options(class_name, hand)
        idxs = list({o[0] for o in options})
        rng.shuffle(idxs)
        chosen_idxs = idxs[:3]
        form = {}
        for round_num, hand_idx in enumerate(chosen_idxs):
            variant = next(o[2] for o in options if o[0] == hand_idx)
            form[f"round_{round_num}"] = f"{hand_idx}|{variant}"
        if M.HAS_STANCE[class_name]:
            form["stance"] = rng.choice(["G", "C"])
        resp = client.post("/combat_plan/submit", data=form, follow_redirects=True)
        if PW._S["phase"] != "combat_plan":
            return resp
    raise RuntimeError(f"combat plan rejected {max_attempts} times in a row -- real bug, not luck")


def run_scripted_session(class_name, seed, max_steps=120, verbose=False):
    rng = random.Random(seed + 5000)
    client = PW.app.test_client()
    try:
        resp = client.post("/start", data={"class_name": class_name, "seed": str(seed)},
                            follow_redirects=True)
        if resp.status_code != 200:
            return False, f"start failed: {resp.status_code}"

        for step in range(max_steps):
            phase = PW._S["phase"]
            if phase == "town":
                hero = PW._S["board"].heroes[0]
                actions = BE.get_town_actions(hero, PW._S["purchase_queues"][0])
                idx = rng.randrange(len(actions))
                resp = client.post("/town/action", data={"idx": str(idx)}, follow_redirects=True)
            elif phase == "trainer":
                hero = PW._S["board"].heroes[0]
                actions = BE.get_town_actions(hero, PW._S["purchase_queues"][0])
                idx = rng.randrange(len(actions))
                resp = client.post("/trainer/action", data={"idx": str(idx)}, follow_redirects=True)
            elif phase == "travel":
                idx = _pick_travel_action(rng)
                resp = client.post("/travel/action", data={"idx": str(idx)}, follow_redirects=True)
            elif phase == "scouted_pick":
                pick = rng.choice(["0", "1"])
                resp = client.post("/scouted_pick/choose", data={"pick": pick}, follow_redirects=True)
            elif phase == "combat_plan":
                resp = client.get("/combat_plan")  # ensure hand/pending state is populated
                resp = _submit_combat_plan(client, rng)
            elif phase == "combat_result":
                resp = client.post("/combat_plan/continue", data={}, follow_redirects=True)
            else:
                return False, f"unexpected phase {phase!r} at step {step}"

            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code} at step {step} (phase was {phase!r})"
            if verbose:
                print(f"  step {step}: phase={phase} -> now {PW._S['phase']}")
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _submit_active_combat_plan(client, rng, submit_url, max_attempts=20):
    """A rejected submission re-renders the SAME hero's cmp_combat_plan page (phase stays
    'cmp_combat_plan', active_hero_idx unchanged) -- but a SUCCESSFUL submission can also land
    on 'cmp_combat_plan' if the resolve queue's next hero also needs a combat plan (competitive
    mode resolves multiple heroes' pulls in sequence, task #78). Success is therefore "phase
    changed OR active_hero_idx changed," not just "phase changed" -- conflating the two here
    was a real test-harness bug (not a product bug): it kept resubmitting a DIFFERENT hero's
    turn using the first hero's stale class_name/hand, which could of course keep failing."""
    hero_idx = PW._S["active_hero_idx"]
    for _attempt in range(max_attempts):
        class_name = PW._S["class_names"][PW._S["active_hero_idx"]]
        hand = PW._S["pending_hand"]
        options = PW._hand_options(class_name, hand)
        idxs = list({o[0] for o in options})
        rng.shuffle(idxs)
        chosen_idxs = idxs[:3]
        form = {}
        for round_num, hidx in enumerate(chosen_idxs):
            variant = next(o[2] for o in options if o[0] == hidx)
            form[f"round_{round_num}"] = f"{hidx}|{variant}"
        if M.HAS_STANCE[class_name]:
            form["stance"] = rng.choice(["G", "C"])
        resp = client.post(submit_url, data=form, follow_redirects=True)
        if PW._S["phase"] != "cmp_combat_plan" or PW._S["active_hero_idx"] != hero_idx:
            return resp
    raise RuntimeError(f"competitive combat plan rejected {max_attempts} times in a row")


def run_scripted_competitive_session(specs, seed, max_rounds=6, verbose=False):
    """specs: list of (class_name, controller) pairs, 2-4 entries. Scripts every human seat's
    choices, exercising Town, declare, Scouted Pull pick, and combat plan pages across a mixed
    human/AI party -- same "dumb but always-legal" stand-in approach as run_scripted_session."""
    rng = random.Random(seed + 7000)
    client = PW.app.test_client()
    try:
        form = {"seed": str(seed)}
        for i, (class_name, controller) in enumerate(specs):
            form[f"class_{i}"] = class_name
            form[f"controller_{i}"] = controller
        resp = client.post("/party/start", data=form, follow_redirects=True)
        if resp.status_code != 200:
            return False, f"party start failed: {resp.status_code}"

        steps = 0
        max_steps = max_rounds * (len(specs) * 6 + 4)
        while PW._S["round_num"] <= max_rounds:
            steps += 1
            if steps > max_steps:
                return False, f"exceeded step budget ({max_steps}) without finishing {max_rounds} rounds"
            phase = PW._S["phase"]
            if phase == "cmp_town":
                hero_idx = PW._S["active_hero_idx"]
                hero = PW._S["board"].heroes[hero_idx]
                actions = BE.get_town_actions(hero, PW._S["purchase_queues"][hero_idx])
                idx = rng.randrange(len(actions))
                resp = client.post("/cmp/town/action", data={"idx": str(idx)}, follow_redirects=True)
            elif phase == "cmp_trainer":
                hero_idx = PW._S["active_hero_idx"]
                hero = PW._S["board"].heroes[hero_idx]
                actions = BE.get_town_actions(hero, PW._S["purchase_queues"][hero_idx])
                idx = rng.randrange(len(actions))
                resp = client.post("/cmp/trainer/action", data={"idx": str(idx)}, follow_redirects=True)
            elif phase == "cmp_declare":
                hero_idx = PW._S["active_hero_idx"]
                hero = PW._S["board"].heroes[hero_idx]
                actions = BE.get_travel_actions(hero, PW._S["board"], PW._S["rng"])
                idx = rng.randrange(len(actions))
                resp = client.post("/cmp/declare/action", data={"idx": str(idx)}, follow_redirects=True)
            elif phase == "cmp_scouted_pick":
                pick = rng.choice(["0", "1"])
                resp = client.post("/cmp/scouted_pick/choose", data={"pick": pick}, follow_redirects=True)
            elif phase == "cmp_combat_plan":
                client.get("/cmp/combat_plan")
                resp = _submit_active_combat_plan(client, rng, "/cmp/combat_plan/submit")
            elif phase == "cmp_pvp_initiate":
                resp = client.post("/cmp/pvp/declare_peace", data={}, follow_redirects=True)
            elif phase == "cmp_pvp_plan":
                hero_idx = PW._S["active_hero_idx"]
                hand = PW._S[f"pvp_hand_{hero_idx}"]
                import random as rnd
                plan = rnd.sample(hand, 3)
                data = {f"card_{i}": c for i, c in enumerate(plan)}
                resp = client.post("/cmp/pvp/plan/submit", data=data, follow_redirects=True)
            elif phase == "cmp_round_result":
                resp = client.post("/cmp/round_result/continue", data={}, follow_redirects=True)
            else:
                return False, f"unexpected phase {phase!r} at step {steps}"

            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code} at step {steps} (phase was {phase!r})"
            if verbose:
                print(f"  step {steps}: round={PW._S['round_num']} phase={phase} -> now {PW._S['phase']}")
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def run_all(verbose=False):
    failures = []
    for class_name in M.CARD_SOURCE:
        for seed in range(3):
            ok, err = run_scripted_session(class_name, seed, verbose=verbose)
            status = "ok" if ok else f"FAIL: {err}"
            print(f"{class_name:12s} seed={seed}  {status}")
            if not ok:
                failures.append((class_name, seed, err))
    classes = list(M.CARD_SOURCE.keys())
    party_scenarios = [
        [(classes[0], "human"), (classes[1], "ai")],
        [(classes[2], "human"), (classes[3], "ai"), (classes[4], "ai")],
        [(classes[5], "human"), (classes[6], "human"), (classes[7], "ai")],
        [(c, "ai") for c in classes[:4]],
    ]
    for specs in party_scenarios:
        for seed in range(3):
            ok, err = run_scripted_competitive_session(specs, seed, verbose=verbose)
            desc = ",".join(f"{c}:{ctrl}" for c, ctrl in specs)
            status = "ok" if ok else f"FAIL: {err}"
            print(f"[competitive] {desc}  seed={seed}  {status}")
            if not ok:
                failures.append((desc, seed, err))

    print(f"\n{len(failures)} failures" if failures else "\nAll scripted web sessions completed cleanly")
    return not failures


if __name__ == "__main__":
    ok = run_all()
    raise SystemExit(0 if ok else 1)
