import unittest
from generate_tickets import generate, BANKS
from ticket_triage import CATEGORIES


class TestGenerator(unittest.TestCase):
    def test_reproducible_with_same_seed(self):
        self.assertEqual(generate(seed=7), generate(seed=7))

    def test_different_seed_gives_different_data(self):
        self.assertNotEqual(generate(seed=7)[0], generate(seed=8)[0])

    def test_labels_are_valid_and_ids_match(self):
        tickets, labels = generate()
        self.assertEqual([t[0] for t in tickets], [l[0] for l in labels])
        self.assertEqual(len({t[0] for t in tickets}), len(tickets))
        for l in labels:
            self.assertIn(l[3], CATEGORIES)

    def test_benchmark_includes_hard_cases(self):
        _, labels = generate()
        cats = {l[3] for l in labels}
        self.assertIn("Security incident", cats)
        self.assertIn("Other / Unclear", cats)

    def test_heldout_set_is_reproducible_and_uses_different_templates(self):
        groups, seed, _ = BANKS["heldout"]
        self.assertEqual(generate(seed, groups), generate(seed, groups))
        main_titles = {tpl[0] for g_, _ in BANKS["main"][0] for tpl in g_}
        held_titles = {tpl[0] for g_, _ in groups for tpl in g_}
        self.assertEqual(main_titles & held_titles, set())


if __name__ == "__main__":
    unittest.main()
