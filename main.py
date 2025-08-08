# main.py
import os
import time
import signal
import traceback
from datetime import datetime, timezone

from langgraph.graph import StateGraph, END

from agents.researcher import researcher_node
from agents.curator import curator_node
from agents.writer import writer_node
from agents.editor import editor_node
from agents.publisher import publisher_node

# ---------- Config ----------
SLEEP_SECS = int(os.getenv("WORKER_SLEEP_SECS", "7200"))  # pauza između ciklusa (default 2h)
HEARTBEAT_EVERY = int(os.getenv("HEARTBEAT_EVERY", "60"))  # heartbeat na X sekundi
MAX_BACKOFF = int(os.getenv("MAX_BACKOFF", "300"))  # max backoff 5 min

SHUTDOWN = False


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")


def _handle_signal(signum, _frame):
    global SHUTDOWN
    SHUTDOWN = True
    print(f"[worker] {_now()} got signal {signum}, shutting down...", flush=True)


for _sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(_sig, _handle_signal)


# ---------- LangGraph ----------
def build_app():
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


# ---------- One cycle ----------
def one_cycle(app):
    print(f"[worker] {_now()} cycle start", flush=True)
    init_state = {}
    try:
        final_state = app.invoke(init_state)
        status = final_state.get("status")
        post_id = final_state.get("post_id")
        post_link = final_state.get("post_link")
        print(f"[worker] {_now()} cycle done - status={status} post_id={post_id} link={post_link}", flush=True)
    except Exception as e:
        print(f"[worker] {_now()} cycle error: {e}", flush=True)
        traceback.print_exc()
        raise


# ---------- Main loop ----------
def main_loop():
    app = build_app()
    backoff = 5

    while not SHUTDOWN:
        try:
            one_cycle(app)
            backoff = 5  # reset posle uspeha

            elapsed = 0
            while elapsed < SLEEP_SECS and not SHUTDOWN:
                if elapsed % HEARTBEAT_EVERY == 0:
                    remaining = SLEEP_SECS - elapsed
                    print(f"[worker] {_now()} alive - waiting {remaining}s", flush=True)
                time.sleep(1)
                elapsed += 1

        except Exception:
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
