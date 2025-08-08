import os, time, signal, sys, traceback

SHUTDOWN = False

def handle_signal(signum, frame):
    # uredan prekid (Render po redeploy/scale šalje SIGTERM)
    global SHUTDOWN
    SHUTDOWN = True
    print(f"[worker] got signal {signum}, shutting down...", flush=True)

for sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(sig, handle_signal)

def one_cycle():
    # >>> ovde stavi tvoj jedan ciklus: reddit -> AI -> wordpress <<<
    print("[worker] cycle start", flush=True)
    # ... tvoja logika ...
    print("[worker] cycle done", flush=True)

def main_loop():
    sleep_secs = 7200  # 2h
    backoff = 5
    while not SHUTDOWN:
        try:
            one_cycle()
            backoff = 5
            elapsed = 0
            while elapsed < sleep_secs and not SHUTDOWN:
                # heartbeat svake minute
                if elapsed % 60 == 0:
                    print(f"[worker] alive - waiting {sleep_secs - elapsed}s", flush=True)
                time.sleep(1)
                elapsed += 1
        except Exception as e:
            print("[worker] cycle error:", e, flush=True)
            traceback.print_exc()
            time.sleep(min(backoff, 300))
            backoff = min(backoff * 2, 300)

if __name__ == "__main__":
    print("[worker] starting...", flush=True)
    main_loop()
    print("[worker] stopped.", flush=True)
