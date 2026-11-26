"""Command line.

  python3 -m vs fetch                       download and verify every pinned input
  python3 -m vs commitment                  show the held-out commitment
  python3 -m vs verify-reveal <seed>        check a revealed seed against the commitment
  python3 -m vs facts [--split S]           run the L2 battery
  python3 -m vs judge KEY.json [--split S]  judge one submission
  python3 -m vs season [--split S]          the test's own calibration (positive controls, red-team decoders)
  python3 -m vs experiment PATH             validate and run one experiment directory (advisory)
  python3 -m vs score PATH --pr URL         scorer only: judge on held-out pages, put on the record
  python3 -m vs dispatch "TEXT"             the lead seat's public update

S is practice (default, public), heldout (scorer only) or all.
"""
import argparse, json, os, sys


def main(argv=None):
    os.environ.setdefault("PYTHONHASHSEED", "0")
    ap = argparse.ArgumentParser(prog="vs", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd")
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--split", default="practice", choices=["practice", "heldout", "all"])
    ap.add_argument("--port", type=int, default=8408)
    ap.add_argument("--pr", default=None)
    ap.add_argument("--parts", default="controls,redteam")
    a = ap.parse_args(argv)

    if a.cmd == "fetch":
        from .fetch import fetch
        fetch()
    elif a.cmd == "commitment":
        from . import path
        print(open(path("heldout", "COMMITMENT.json")).read())
    elif a.cmd == "verify-reveal":
        from . import split
        ok, held = split.verify(a.arg)
        print("MATCHES the commitment" if ok else "DOES NOT MATCH the commitment")
        if ok:
            print(",".join(held))
    elif a.cmd == "facts":
        from . import corpus, facts
        from .fetch import verify
        verify()
        tr, ev = corpus.split_pages(a.split)
        results = facts.run(tr, ev)
        if not results:
            print("No registered facts.")
        for k, v in results.items():
            print(k, "ESTABLISHED" if v["pass"] else "REFUTED   ", v["value"])
    elif a.cmd == "judge":
        from . import corpus, judge
        from .fetch import verify
        verify()
        tr, ev = corpus.split_pages(a.split)
        r = judge.evaluate(judge.load_key(a.arg), tr, ev, a.split)
        json.dump(r, sys.stdout, indent=1, ensure_ascii=False, default=str)
        print()
        print(f"\nVERDICT: {r['verdict']}" + (f"  (failed: {', '.join(r['failed'])})" if r["failed"] else ""))
    elif a.cmd == "season":
        from . import season
        from .fetch import verify
        verify()
        season.run(a.split, parts=tuple(a.parts.split(",")))
    elif a.cmd == "site":
        from . import site
        site.build()
    elif a.cmd == "desk":
        from .desk import server
        server.serve(a.port)
    elif a.cmd == "dispatch":
        # the lead seat's public update: python3 -m vs dispatch "text"
        from . import registry
        it = registry.add({"id": registry.next_id("D"), "type": "dispatch", "title": a.arg.split(". ")[0][:120],
                           "statement": a.arg, "verdict": "POSTED", "value": None, "detail": {}, "program": "lead",
                           "provenance": {"added_by": "swarm-lead", "how": "lead", "pr": None, "files": []}})
        print(it["id"])
    elif a.cmd == "score":
        from . import score
        from .fetch import verify
        verify()
        pr = sys.argv[sys.argv.index("--pr") + 1] if "--pr" in sys.argv else None
        r = score.score(a.arg, pr)
        print(json.dumps(r, indent=1, default=str))
    elif a.cmd == "experiment":
        from . import experiment
        sys.exit(experiment.main(a.arg, a.split))
    else:
        ap.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
