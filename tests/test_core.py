import threading
import unittest

from thread_local_context_utils import ContextCarrier, current_context, new_context


class ContextCarrierTests(unittest.TestCase):
    def test_set_and_get_in_same_thread(self):
        ctx = new_context()
        ctx.set("user", "alice")
        self.assertEqual(ctx.get("user"), "alice")
        self.assertIsNone(ctx.get("missing"))
        self.assertEqual(ctx.get("missing", "fallback"), "fallback")

    def test_delete_removes_key(self):
        ctx = new_context()
        ctx.set("k", 1)
        ctx.delete("k")
        self.assertNotIn("k", ctx)
        with self.assertRaises(KeyError):
            ctx.delete("k")

    def test_clear_removes_all_keys(self):
        ctx = new_context()
        ctx.set("a", 1)
        ctx.set("b", 2)
        ctx.clear()
        self.assertEqual(len(ctx), 0)
        self.assertEqual(list(ctx.keys()), [])

    def test_snapshot_is_a_copy(self):
        ctx = new_context()
        ctx.set("a", 1)
        snap = ctx.snapshot()
        snap["a"] = 99
        self.assertEqual(ctx.get("a"), 1)

    def test_restore_replaces_existing_values(self):
        ctx = new_context()
        ctx.set("stale", "old")
        ctx.restore({"fresh": "new"})
        self.assertNotIn("stale", ctx)
        self.assertEqual(ctx.get("fresh"), "new")

    def test_restore_copies_input(self):
        ctx = new_context()
        source = {"x": 1}
        ctx.restore(source)
        source["x"] = 2
        self.assertEqual(ctx.get("x"), 1)

    def test_threads_are_isolated(self):
        ctx = new_context()
        ctx.set("shared", "main")
        observed = []

        def worker():
            observed.append(ctx.get("shared"))
            ctx.set("shared", "worker")
            observed.append(ctx.get("shared"))

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        self.assertEqual(observed, [None, "worker"])
        self.assertEqual(ctx.get("shared"), "main")

    def test_snapshot_and_restore_across_threads(self):
        ctx = new_context()
        ctx.set("request_id", "r-1")
        ctx.set("user", "bob")
        result = {}

        def worker():
            result["before"] = ctx.snapshot()
            ctx.restore({"request_id": "r-1", "user": "bob", "extra": True})
            result["during"] = ctx.snapshot()
            ctx.restore({})
            result["after"] = ctx.snapshot()

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertEqual(result["before"], {})
        self.assertEqual(
            result["during"], {"request_id": "r-1", "user": "bob", "extra": True}
        )
        self.assertEqual(result["after"], {})
        # Parent thread is untouched.
        self.assertEqual(ctx.snapshot(), {"request_id": "r-1", "user": "bob"})

    def test_two_carriers_do_not_share_storage(self):
        a = new_context()
        b = new_context()
        a.set("key", "a")
        b.set("key", "b")
        self.assertEqual(a.get("key"), "a")
        self.assertEqual(b.get("key"), "b")

    def test_current_context_is_shared(self):
        ctx = current_context()
        ctx.set("global_key", 42)
        self.assertEqual(current_context().get("global_key"), 42)
        # Clean up so other tests are not affected.
        ctx.clear()

    def test_contains_and_len(self):
        ctx = new_context()
        self.assertNotIn("a", ctx)
        self.assertEqual(len(ctx), 0)
        ctx.set("a", 1)
        ctx.set("b", 2)
        self.assertIn("a", ctx)
        self.assertEqual(len(ctx), 2)


if __name__ == "__main__":
    unittest.main()
