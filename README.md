# state_machine

A small finite state machine that rejects transitions not declared in its transition table.

```python
from state_machine import StateMachine, States, TransitionError

states = States(
    ["idle", "running", "done"],
    [("idle", "running"), ("running", "done"), ("running", "idle")],
    initial="idle",
)
m = StateMachine(states)
m.transition("running")
m.transition("done")
```

## Why

The problem this solves is narrow: an object whose lifecycle moves between a
fixed set of states along a fixed set of edges, and where attempting an
undeclared edge should fail loudly rather than silently no-op. The trade-off is
that the transition table is static and fully known at construction time. You
cannot express conditional transitions ("allowed only if some flag is set").
If you need that, put the condition outside the machine and only call
`transition` when the condition holds.

## Edge cases

- A transition from a state to itself is rejected unless explicitly declared.
- `on_exit` callbacks fire before the internal state changes; `on_enter`
  callbacks fire after. If `on_exit` raises, the transition is aborted and the
  state is unchanged. If `on_enter` raises, the state has already changed and
  is **not** rolled back — `on_exit` for the source has already run.
- `reset()` returns the machine to its initial state without consulting the
  transition table and without firing callbacks. It is an escape hatch, not a
  normal transition.

## Exports

- `States` — declares the state set, transition table, and initial state.
- `StateMachine` — holds the current state and performs transitions.
- `TransitionError` — raised on any undeclared transition.

## Running the tests

```
PYTHONPATH=src python -m unittest discover -s tests
```
