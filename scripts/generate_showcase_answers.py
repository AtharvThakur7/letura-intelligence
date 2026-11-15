"""Run every suggested question once with the LIVE analyst and store the answers.

    python scripts/generate_showcase_answers.py

Needs MySQL + a valid OPENAI_API_KEY with AI_ENABLED=true. Uses a few cents of credits
(~26 questions). Output: data/snapshot/ai_showcase.json (commit it to publish).
"""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
logging.disable(logging.WARNING)

from letura.ai.analyst import SUGGESTED_QUESTIONS, Analyst  # noqa: E402
from letura.ai.showcase import SHOWCASE_PATH  # noqa: E402
from letura.analytics.filters import FilterState  # noqa: E402


def main() -> int:
    a = Analyst()
    if a.mode != "live":
        print("Live AI is not available (check AI_ENABLED=true and OPENAI_API_KEY in .env). Nothing written.")
        return 1
    print(a.status_text())
    questions = [q for qs in SUGGESTED_QUESTIONS.values() for q in qs]
    out, tokens, failed = {}, 0, []
    if "--all" not in sys.argv and SHOWCASE_PATH.exists():      # default: only fill in missing answers
        out = json.loads(SHOWCASE_PATH.read_text(encoding="utf-8")).get("answers", {})
        print(f"Keeping {len(out)} stored answers (use --all to regenerate everything)")
    for i, q in enumerate(questions, 1):
        if q in out:
            continue
        reply = None
        for attempt in range(2):
            reply = a.answer(q, [], FilterState(), True)
            if reply.mode == "live" and reply.results and all(r.ok for r in reply.results):
                break
            time.sleep(2)
        ok = reply.mode == "live" and reply.results and all(r.ok for r in reply.results)
        print(f"[{i:02d}/{len(questions)}] {'OK ' if ok else 'SKIP'} {q[:70]} ({reply.tokens} tokens, {len(reply.results)} tools)")
        if not ok:
            failed.append(q)
            continue
        tokens += reply.tokens
        out[q] = {"text": reply.text, "model": a.s.model, "generated_at": datetime.now().isoformat(timespec="seconds"),
                  "tool_calls": reply.tool_calls, "results": [r.model_dump() for r in reply.results]}
    SHOWCASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SHOWCASE_PATH.write_text(json.dumps({"answers": out}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\nStored {len(out)}/{len(questions)} answers, {tokens:,} tokens -> {SHOWCASE_PATH}")
    if failed:
        print("Not stored:", *failed, sep="\n  - ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
