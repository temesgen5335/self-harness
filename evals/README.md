# Review evals

Does a headless `/wf-review` catch known defects, and does it give the same answer twice?

**Status: built and unit-tested, not yet run against a model.** No catch rates are claimed until a run is committed to `results/`.

## Cases

Each case is the shared `fixture/` app (a small multi-tenant shop) plus one change from `cases/<name>/change/`,
committed on top. The change's own tests pass, so a reviewer has to read the code to find the defect.

| Case | Seeded defect | Expected lens |
|---|---|---|
| `sql-injection` | User name formatted into the SQL string | security |
| `race` | Check-then-act on stock without the lock it declares | correctness, scale |
| `missing-ac-test` | AC-2 (50% discount cap) implemented with no test | correctness, design |
| `unbounded-query` | Orders page loads every order of a 5M-order tenant | scale, correctness |
| `swallowed-error` | Gateway errors swallowed and reported as a successful charge | correctness, operability |
| `clean-control` | None; measures false blocks | — |

`case.json` holds the brief, the acceptance criteria (written into an approved spec) and the defect's file and keywords.
A defect counts as caught when one finding names its file and contains one of its keywords.

## Run

```bash
python3 -I evals/run_evals.py --dry-run                  # free: builds every fixture and runs its tests
python3 -I evals/run_evals.py --case sql-injection        # one real review
python3 -I evals/run_evals.py --runs 3                    # all cases three times (G2 consistency)
python3 -I evals/run_evals.py --model <model> --keep      # pin the model; keep the repos to read the reviews
```

Each run is a full review (every lens and the adversary) in a throwaway repo, so it costs real tokens; the
summary prints the cost per case. Results are written to `results/<utc time>.json`: commit the ones you rely on.

## Reading the summary

| Column | Meaning | Good |
|---|---|---|
| caught | runs where the defect was found | every run |
| lens | runs where the expected lens found it | most runs |
| blocked | runs where the gate did not pass | every run for seeded cases; none for `clean-control` |
| agree | share of runs with the majority verdict | 100% |
| exposure | range of the matched finding's `p_trigger × p_visible` across runs | narrow |

Keyword matching is coarse: read the kept reviews before trusting a surprising number. Add a case for every
defect class a real review missed.
