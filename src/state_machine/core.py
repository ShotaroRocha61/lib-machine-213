from __future__ import annotations

from typing import Any, Callable, Dict, FrozenSet, Hashable, Iterable, Mapping, Optional, Tuple


class TransitionError(Exception):
    """Raised when a transition is attempted that the machine does not permit.

    We raise rather than silently no-op so that callers cannot accidentally fall
    through to code that assumes the state changed. A no-op transition hides
    bugs; an exception surfaces them immediately.
    """


class States:
    """A declared set of states plus the transitions allowed between them.

    Building the transition table up front (rather than accepting a predicate
    function per transition) means the entire reachable state space is known
    at construction time. This makes it possible to validate the table once and
    reject impossible transitions with a simple lookup at runtime — O(1) and
    free of side effects.
    """

    __slots__ = ("_states", "_transitions", "_initial")

    def __init__(
        self,
        states: Iterable[Hashable],
        transitions: Optional[Iterable[Tuple[Hashable, Hashable]]] = None,
        *,
        initial: Hashable,
    ) -> None:
        state_set: FrozenSet[Hashable] = frozenset(states)
        if not state_set:
            raise ValueError("states must not be empty")
        if initial not in state_set:
            raise ValueError(f"initial state {initial!r} is not in states")

        # Store transitions as a dict of frozensets so membership checks are
        # O(1) and the structure is immutable after construction.
        trans: Dict[Hashable, FrozenSet[Hashable]] = {s: frozenset() for s in state_set}
        if transitions is not None:
            for src, dst in transitions:
                if src not in state_set:
                    raise ValueError(f"transition source {src!r} is not a declared state")
                if dst not in state_set:
                    raise ValueError(f"transition target {dst!r} is not a declared state")
                trans[src] = trans[src] | frozenset((dst,))

        self._states: FrozenSet[Hashable] = state_set
        self._transitions: Mapping[Hashable, FrozenSet[Hashable]] = trans
        self._initial: Hashable = initial

    @property
    def states(self) -> FrozenSet[Hashable]:
        return self._states

    @property
    def initial(self) -> Hashable:
        return self._initial

    def can_transition(self, src: Hashable, dst: Hashable) -> bool:
        if src not in self._states or dst not in self._states:
            return False
        return dst in self._transitions[src]

    def targets_from(self, src: Hashable) -> FrozenSet[Hashable]:
        if src not in self._states:
            raise KeyError(src)
        return self._transitions[src]

    def __repr__(self) -> str:
        return f"States(states={set(self._states)!r}, initial={self._initial!r})"


class StateMachine:
    """A finite state machine that rejects transitions not in its declared table.

    The machine holds a current state and exposes :meth:`transition` to move to
    a new one. Any transition not explicitly declared in the :class:`States`
    definition raises :class:`TransitionError` and leaves the current state
    untouched.

    Optional ``on_enter`` and ``on_exit`` callbacks may be registered per
    state. Callbacks receive the source state, target state, and the event
    payload (``None`` if omitted). Callbacks are called *after* the state has
    been validated but the internal state is updated *before* callbacks run,
    so a callback that inspects ``machine.state`` sees the new state. If an
    ``on_exit`` callback raises, the transition is aborted and the state is
    rolled back; if an ``on_enter`` callback raises the state is *not* rolled
    back because ``on_exit`` for the source has already fired. This asymmetry is
    documented here so callers know not to rely on atomicity across callbacks.
    """

    __slots__ = ("_states", "_current", "_on_enter", "_on_exit")

    def __init__(
        self,
        states: States,
        *,
        on_enter: Optional[Mapping[Hashable, Callable[..., Any]]] = None,
        on_exit: Optional[Mapping[Hashable, Callable[..., Any]]] = None,
    ) -> None:
        self._states: States = states
        self._current: Hashable = states.initial
        self._on_enter: Dict[Hashable, Callable[..., Any]] = dict(on_enter) if on_enter else {}
        self._on_exit: Dict[Hashable, Callable[..., Any]] = dict(on_exit) if on_exit else {}

        for s in self._on_enter:
            if s not in states.states:
                raise ValueError(f"on_enter references unknown state {s!r}")
        for s in self._on_exit:
            if s not in states.states:
                raise ValueError(f"on_exit references unknown state {s!r}")

    @property
    def state(self) -> Hashable:
        return self._current

    @property
    def states(self) -> States:
        return self._states

    def can_transition(self, dst: Hashable) -> bool:
        return self._states.can_transition(self._current, dst)

    def transition(self, dst: Hashable, payload: Any = None) -> Hashable:
        """Transition to ``dst``, raising :class:`TransitionError` if not allowed.

        On success returns the new state. On failure the current state is
        unchanged and no callbacks fire.
        """
        src = self._current
        if not self._states.can_transition(src, dst):
            raise TransitionError(
                f"transition from {src!r} to {dst!r} is not permitted"
            )

        # Fire on_exit for the source first. If it raises, roll back nothing
        # (state hasn't changed yet) and let the exception propagate.
        exit_cb = self._on_exit.get(src)
        if exit_cb is not None:
            exit_cb(src, dst, payload)

        self._current = dst

        enter_cb = self._on_enter.get(dst)
        if enter_cb is not None:
            enter_cb(src, dst, payload)

        return dst

    def reset(self) -> Hashable:
        """Return the machine to its declared initial state without callbacks.

        Reset bypasses the transition table and callbacks deliberately: it is
        an escape hatch for teardown/restart, not a normal state change.
        """
        self._current = self._states.initial
        return self._current

    def __repr__(self) -> str:
        return f"StateMachine(states={self._states!r}, current={self._current!r})"
