"""
Benchmark corenum/threadnum combinations for hourly_cutoff.compute().

Run on the target machine (e.g. the Raspberry Pi):
    OTSOenv/bin/python bench_cores.py [repeats]

Only combinations with corenum * threadnum <= the CPU count are tested.
The live data files are cached by OTSO for an hour, so every run sees the same inputs.
"""

import os
import sys
import time
from datetime import datetime, timedelta, timezone

from hourly_cutoff import LAG_HOURS, compute

COMBOS = [(1, 1), (2, 1), (4, 1), (1, 2), (1, 4), (2, 2)]


def main() -> int:
    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    ncpu = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()
    event_time = (datetime.now(timezone.utc) - timedelta(hours=LAG_HOURS)).replace(minute=0, second=0, microsecond=0, tzinfo=None)

    print(f"{ncpu} CPUs available, {repeats} repeats, event time {event_time}")
    print(f"{'corenum':>7} {'threadnum':>9} {'best_s':>8} {'mean_s':>8}  Rc (GV)")

    reference = None
    for corenum, threadnum in COMBOS:
        if corenum * threadnum > ncpu:
            continue
        times = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            df, _ = compute(event_time, corenum=corenum, threadnum=threadnum)
            times.append(time.perf_counter() - t0)
        rc = df.loc["Rc"].to_dict()
        if reference is None:
            reference = rc
        flag = "" if rc == reference else "  <-- differs from first combo"
        print(f"{corenum:>7} {threadnum:>9} {min(times):>8.1f} {sum(times)/len(times):>8.1f}  {rc}{flag}",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
