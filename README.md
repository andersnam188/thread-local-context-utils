# thread-local-context-utils

A carrier object that propagates request-scoped values across threads using
`threading.local`, with explicit `snapshot()` and `restore()` for child tasks.

## Usage

```python
from thread_local_context_utils import new_context

ctx = new_context()
ctx.set("request_id", "r-1")
ctx.set("user", "alice")

# In a child thread, copy the parent's values, do work, then restore.
import threading

def worker():
    parent = ctx.snapshot()          # {"request_id": "r-1", "user": "alice"}
    ctx.restore(parent)
    ctx.set("worker", True)
    # ... do work ...
    ctx.restore({})                  # clear this thread's view

t = threading.Thread(target=worker)
t.start()
t.join()

assert ctx.get("request_id") == "r-1"  # parent thread is unchanged
```

## Why this exists

`threading.local` gives every thread its own storage, which is exactly what you
want for request-scoped values in a threaded server.  The awkward part is that
a child thread starts with an empty context, so the request id, authenticated
user, and tracing span set by the parent are invisible there.  Passing them as
function arguments works but is invasive; implicit inheritance (copying on
thread start) is surprising and hard to undo.

This library chooses the explicit route: the parent calls `snapshot()` and the
child calls `restore()`.  Nothing is copied automatically.  The trade-off is
that the caller must remember to restore the child's original state when the
child finishes, but in return the propagation is visible in the code and never
leaks values into long-lived worker threads.

## Awkward edge

`restore()` replaces the entire current-thread mapping.  If a child thread had
values of its own before restoring the parent's snapshot, those values are
discarded.  Take a snapshot of the child's state first if you need to keep it.

## API

* `ContextCarrier` — a per-thread mapping with `get`, `set`, `delete`,
  `clear`, `snapshot`, `restore`, `keys`, `__contains__`, and `__len__`.
* `new_context()` — create a fresh, independent carrier.
* `current_context()` — return a process-wide default carrier for applications
  that only need one context.
