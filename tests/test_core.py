import unittest

from state_machine import StateMachine, States, TransitionError


class StatesTests(unittest.TestCase):
    def test_initial_must_be_a_declared_state(self):
        with self.assertRaises(ValueError):
            States(["a", "b"], initial="c")

    def test_states_must_not_be_empty(self):
        with self.assertRaises(ValueError):
            States([], initial="a")

    def test_transition_source_must_be_declared(self):
        with self.assertRaises(ValueError):
            States(["a", "b"], [("c", "a")], initial="a")

    def test_transition_target_must_be_declared(self):
        with self.assertRaises(ValueError):
            States(["a", "b"], [("a", "c")], initial="a")

    def test_can_transition_true_for_declared(self):
        s = States(["a", "b"], [("a", "b")], initial="a")
        self.assertTrue(s.can_transition("a", "b"))

    def test_can_transition_false_for_undeclared(self):
        s = States(["a", "b"], [("a", "b")], initial="a")
        self.assertFalse(s.can_transition("b", "a"))
        self.assertFalse(s.can_transition("a", "a"))

    def test_can_transition_false_for_unknown_states(self):
        s = States(["a", "b"], [("a", "b")], initial="a")
        self.assertFalse(s.can_transition("a", "z"))
        self.assertFalse(s.can_transition("z", "a"))

    def test_targets_from_returns_declared_targets(self):
        s = States(["a", "b", "c"], [("a", "b"), ("a", "c")], initial="a")
        self.assertEqual(s.targets_from("a"), frozenset({"b", "c"}))

    def test_targets_from_unknown_raises_keyerror(self):
        s = States(["a"], initial="a")
        with self.assertRaises(KeyError):
            s.targets_from("z")

    def test_states_property_is_frozenset(self):
        s = States(["a", "b"], initial="a")
        self.assertEqual(s.states, frozenset({"a", "b"}))

    def test_initial_property(self):
        s = States(["a", "b"], initial="b")
        self.assertEqual(s.initial, "b")


class StateMachineTransitionTests(unittest.TestCase):
    def _machine(self):
        states = States(
            ["idle", "running", "done"],
            [("idle", "running"), ("running", "done"), ("running", "idle")],
            initial="idle",
        )
        return StateMachine(states)

    def test_starts_at_initial(self):
        m = self._machine()
        self.assertEqual(m.state, "idle")

    def test_valid_transition_updates_state(self):
        m = self._machine()
        m.transition("running")
        self.assertEqual(m.state, "running")

    def test_invalid_transition_raises_and_leaves_state_unchanged(self):
        m = self._machine()
        with self.assertRaises(TransitionError):
            m.transition("done")
        self.assertEqual(m.state, "idle")

    def test_transition_to_same_state_not_allowed_unless_declared(self):
        states = States(["a", "b"], [("a", "b")], initial="a")
        m = StateMachine(states)
        with self.assertRaises(TransitionError):
            m.transition("a")

    def test_self_transition_allowed_when_declared(self):
        states = States(["a", "b"], [("a", "a"), ("a", "b")], initial="a")
        m = StateMachine(states)
        m.transition("a")
        self.assertEqual(m.state, "a")

    def test_can_transition_reflects_current_state(self):
        m = self._machine()
        self.assertTrue(m.can_transition("running"))
        self.assertFalse(m.can_transition("done"))
        m.transition("running")
        self.assertTrue(m.can_transition("done"))
        self.assertTrue(m.can_transition("idle"))

    def test_transition_returns_new_state(self):
        m = self._machine()
        self.assertEqual(m.transition("running"), "running")

    def test_reset_returns_to_initial(self):
        m = self._machine()
        m.transition("running")
        m.reset()
        self.assertEqual(m.state, "idle")


class CallbackTests(unittest.TestCase):
    def test_on_exit_fires_before_state_change(self):
        log = []
        states = States(["a", "b"], [("a", "b")], initial="a")
        m = StateMachine(states, on_exit={"a": lambda src, dst, p: log.append(("exit", src, dst, m.state))})
        m.transition("b")
        self.assertEqual(log, [("exit", "a", "b", "a")])

    def test_on_enter_fires_after_state_change(self):
        log = []
        states = States(["a", "b"], [("a", "b")], initial="a")
        m = StateMachine(states, on_enter={"b": lambda src, dst, p: log.append(("enter", src, dst, m.state))})
        m.transition("b")
        self.assertEqual(log, [("enter", "a", "b", "b")])

    def test_payload_passed_to_callbacks(self):
        log = []
        states = States(["a", "b"], [("a", "b")], initial="a")
        m = StateMachine(
            states,
            on_exit={"a": lambda src, dst, p: log.append(p)},
            on_enter={"b": lambda src, dst, p: log.append(p)},
        )
        m.transition("b", payload={"key": 1})
        self.assertEqual(log, [{"key": 1}, {"key": 1}])

    def test_on_exit_raising_aborts_transition(self):
        def boom(src, dst, p):
            raise RuntimeError("boom")

        states = States(["a", "b"], [("a", "b")], initial="a")
        m = StateMachine(states, on_exit={"a": boom})
        with self.assertRaises(RuntimeError):
            m.transition("b")
        self.assertEqual(m.state, "a")

    def test_callbacks_only_for_declared_states(self):
        states = States(["a", "b"], [("a", "b")], initial="a")
        with self.assertRaises(ValueError):
            StateMachine(states, on_enter={"z": lambda *a: None})

    def test_no_callbacks_means_no_side_effects(self):
        states = States(["a", "b"], [("a", "b")], initial="a")
        m = StateMachine(states)
        m.transition("b")
        self.assertEqual(m.state, "b")


class HashableStateTests(unittest.TestCase):
    def test_integer_states(self):
        states = States([1, 2, 3], [(1, 2), (2, 3)], initial=1)
        m = StateMachine(states)
        m.transition(2)
        m.transition(3)
        self.assertEqual(m.state, 3)

    def test_tuple_states(self):
        states = States([("doc", "draft"), ("doc", "pub")], [(("doc", "draft"), ("doc", "pub"))], initial=("doc", "draft"))
        m = StateMachine(states)
        m.transition(("doc", "pub"))
        self.assertEqual(m.state, ("doc", "pub"))


if __name__ == "__main__":
    unittest.main()
