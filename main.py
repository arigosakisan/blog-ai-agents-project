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
    sleep_secs = 7200  # 2h između ciklusa
    backoff = 5        # početni backoff na grešku (sek)
    while not SHUTDOWN:
        try:
            one_cycle()
            backoff = 5  # reset backoff-a ako je uspešno
            for _ in range(sleep_secs):
                if SHUTDOWN: break
                time.sleep(1)
        except Exception as e:
            print("[worker] cycle error:", e, flush=True)
            traceback.print_exc()
            # exponential backoff do max 5 min
            time.sleep(min(backoff, 300))
            backoff = min(backoff * 2, 300)

if __name__ == "__main__":
    print("[worker] starting...", flush=True)
    main_loop()
    print("[worker] stopped.", flush=True)
