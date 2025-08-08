# main.py
import os
import time
import signal
import traceback
from datetime import datetime, timezone

# LangGraph
from langgraph.graph import StateGraph, END

# Tvoji agenti
from agents.researcher import researcher_node
from agents.curator import curator_node
from agents.writer import writer_node
from agents.editor import editor_node
from agents.publisher import publisher_node

# -------------------------
# Konfiguracija
# -------------------------

# Pauza između ciklusa (sekunde). Možeš menjati env var-om WORKER_SLEEP_SECS
SLEEP_SECS_DEFAULT = 7200  # 2h
SLEEP_SECS = int(os.getenv("WORKER_SLEEP_SECS", SLEEP_SECS_DEFAULT))

# Maks backoff na grešku (sekunde)
MAX_BACKOFF = 300  # 5 min

# Heartbeat period (sekunde) — na koliko često logujemo da smo "živi"
HEARTBEAT_EVERY = 60

SHUTDOWN = False


def _now() -> str:
    """ISO vreme u UTC (za logove)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")


def handle_signal(signum, frame):
    global SHUTDOWN
    SHUTDOWN = True
    print(f"[worker] {_now()} got signal {signum}, shutting down...", flush=True)


for sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(sig, handle_signal)


# -------------------------
# LangGraph definicija grafa
# -------------------------

def build_app():
    """
    Sastavi LangGraph sa uslovnim granama, pa ga compile-uj.
    Svaki čvor vraća dict i koristimo 'status' polja za rutiranje.
    """
    def route_from_researcher(state: dict):
        return "curator" if state.get("status") == "research_done" else END

    def route_from_curator(state: dict):
        return "writer" if state.get("worthy") else END

    def route_from_writer(state: dict):
        return "editor" if state.get("status") == "draft_ready" else END

    def route_from_editor(state: dict):
        return "publisher" if state.get("status") == "final_ready" else END

    graph = StateGraph(dict)

    graph.add_node("researcher", researcher_node)
    graph.add_node("curator", curator_node)
    graph.add_node("writer", writer_node)
    graph.add_node("editor", editor_node)
    graph.add_node("publisher", publisher_node)

    graph.set_entry_point("researcher")

    graph.add_conditional_edges("researcher", route_from_researcher, {"curator": "curator", END: END})
    graph.add_conditional_edges("curator", route_from_curator, {"writer": "writer", END: END})
    graph.add_conditional_edges("writer", route_from_writer, {"editor": "editor", END: END})
    graph.add_conditional_edges("editor", route_from_editor, {"publisher": "publisher", END: END})
    graph.add_edge("publisher", END)

    app = graph.compile()
    return app


# -------------------------
# Jedan ciklus izvršavanja
# -------------------------

def one_cycle(app):
    """
    Pokreće jedan prolaz grafa. Početni state je prazan dict.
    Svaki agent dopisuje šta treba (npr. original_post, category, draft_article, final_article...).
    """
    print(f"[worker] {_now()} cycle start", flush=True)

    # Početni state po potrebi može imati globalne postavke; ostavljamo prazno.
    init_state = {}

    try:
        # app.invoke vrati finalni state nakon rute do END
        final_state = app.invoke(init_state)

        # Opcioni debug print (kratko)
        status = final_state.get("status")
        post_id = final_state.get("post_id")
        post_link = final_state.get("post_link")
        print(f"[worker] {_now()} cycle done - status={status} post_id={post_id} link={post_link}", flush=True)

    except Exception as e:
        print(f"[worker] {_now()} cycle error: {e}", flush=True)
        traceback.print_exc()
        # Propusti izuzetak do gornjeg handlera (glavna petlja radi backoff)
        raise


# -------------------------
# Glavna petlja 24/7
# -------------------------

def main_loop():
    app = build_app()
    backoff = 5  # početni retry delay u sekundama

    while not SHUTDOWN:
        try:
            one_cycle(app)
            backoff = 5  # reset backoff-a nakon uspešnog ciklusa

            # Pauza između ciklusa sa heartbeat-om
            elapsed = 0
            while elapsed < SLEEP_SECS and not SHUTDOWN:
                if elapsed % HEARTBEAT_EVERY == 0:
                    remaining = SLEEP_SECS - elapsed
                    print(f"[worker] {_now()} alive - waiting {remaining}s", flush=True)
                time.sleep(1)
                elapsed += 1

        except Exception:
            # Greška u ciklusu → exponential backoff, pa pokušaj opet
            delay = min(backoff, MAX_BACKOFF)
            print(f"[worker] {_now()} retry in {delay}s...", flush=True)
            slept = 0
            while slept < delay and not SHUTDOWN:
                time.sleep(1)
                slept += 1
            backoff = min(backoff * 2, MAX_BACKOFF)

    print(f"[worker] {_now()} stopped.", flush=True)


if __name__ == "__main__":
    print(f"[worker] {_now()} starting...", flush=True)
    main_loop()
