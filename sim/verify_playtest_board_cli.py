"""
Smoke test for playtest_board_cli.py -- proves the human-facing driver (Town loop, Travel
loop, scouted-pull reveal-and-pick, card-by-card combat, death/forced-recovery) runs
end-to-end without crashing, across all 9 classes and several seeds, by scripting a "dumb but
always-legal" stand-in for a human player instead of real terminal input.

Not a balance check (this file measures nothing about outcomes) -- it exists purely to catch
plumbing bugs in the new interactive module itself (wrong dict keys, wrong function signatures,
an unhandled outcome shape) before a real human ever sits down with it. Bounds each session to
a fixed number of scripted decisions so a real bug (e.g. an infinite re-prompt loop) fails fast
instead of hanging.
"""
import builtins
import random

import macro_sim as M
import playtest_board_cli as P


def run_scripted_session(class_name, seed, max_inputs=250, verbose=False):
    rng = random.Random(seed + 9000)

    def fake_prompt_choice(prompt, actions, fmt_fn):
        legal = [a for a in actions if a.get("legal", True)]
        return rng.choice(legal)

    call_count = [0]

    def fake_input(prompt=""):
        call_count[0] += 1
        if "Continue" in prompt:
            return "n" if call_count[0] > max_inputs else "y"
        if "face" in prompt:
            return rng.choice(["1", "2"])
        return "0"

    orig_prompt_choice, orig_input = P._prompt_choice, builtins.input
    if not verbose:
        import io
        import contextlib
        sink = io.StringIO()
    try:
        P._prompt_choice = fake_prompt_choice
        builtins.input = fake_input
        if verbose:
            P.play(class_name, seed=seed)
        else:
            with contextlib.redirect_stdout(sink):
                P.play(class_name, seed=seed)
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        P._prompt_choice = orig_prompt_choice
        builtins.input = orig_input


def run_scripted_competitive_session(specs, seed, max_rounds=8, verbose=False):
    """Same scripting approach as run_scripted_session, applied to play_competitive -- also
    scripts the pass-the-device gate (any input advances it) and per-round Scouted-Pull picks.
    max_rounds is small (8, vs. run_scripted_session's much larger turn budget) because a
    competitive round can involve multiple heroes each doing real work -- this is a plumbing
    smoke test, not a pacing measurement, so it doesn't need to run long."""
    rng = random.Random(seed + 9000)

    def fake_prompt_choice(prompt, actions, fmt_fn):
        legal = [a for a in actions if a.get("legal", True)]
        return rng.choice(legal)

    call_count = [0]

    def fake_input(prompt=""):
        call_count[0] += 1
        if "Continue" in prompt:
            return "n" if call_count[0] > 400 else "y"
        if "face" in prompt:
            return rng.choice(["1", "2"])
        return ""  # pass-the-device gate, or any other bare "press Enter" prompt

    orig_prompt_choice, orig_input = P._prompt_choice, builtins.input
    if not verbose:
        import io
        import contextlib
        sink = io.StringIO()
    try:
        P._prompt_choice = fake_prompt_choice
        builtins.input = fake_input
        if verbose:
            P.play_competitive(specs, seed=seed, max_rounds=max_rounds)
        else:
            with contextlib.redirect_stdout(sink):
                P.play_competitive(specs, seed=seed, max_rounds=max_rounds)
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        P._prompt_choice = orig_prompt_choice
        builtins.input = orig_input


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

    print(f"\n{len(failures)} failures" if failures else "\nAll scripted sessions completed cleanly")
    return not failures


if __name__ == "__main__":
    ok = run_all()
    raise SystemExit(0 if ok else 1)
