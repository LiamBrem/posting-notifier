"""
Tests company_match.py, especially the false-positive class found in
production: raw substring matching let short company names (X, Box, IBM)
match unrelated companies that merely contain those letters, which is how
off-list companies were slipping into notifications.
"""
import unittest

from company_match import company_matches, matches_any_target


class TestCompanyMatchesShortNameFalsePositives(unittest.TestCase):
    """The exact bug class that caused off-list companies to notify."""

    def test_x_does_not_match_nutanix(self):
        self.assertFalse(company_matches("Nutanix", "X"))

    def test_box_does_not_match_roblox(self):
        self.assertFalse(company_matches("Roblox", "Box"))

    def test_box_does_not_match_xbox_maker(self):
        self.assertFalse(company_matches("Xbox Game Studios", "Box"))

    def test_ibm_does_not_match_unrelated_company_containing_letters(self):
        self.assertFalse(company_matches("Kibom Robotics", "IBM"))

    def test_x_still_matches_actual_x(self):
        self.assertTrue(company_matches("X", "X"))
        self.assertTrue(company_matches("X Corp", "X"))

    def test_box_still_matches_actual_box(self):
        self.assertTrue(company_matches("Box", "Box"))
        self.assertTrue(company_matches("Box, Inc.", "Box"))


class TestCompanyMatchesGeneral(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(company_matches("Acme", "Acme"))

    def test_field_is_longer_multiword_variant(self):
        self.assertTrue(company_matches("Acme Corporation", "Acme"))

    def test_field_is_shorter_than_multiword_target(self):
        self.assertTrue(company_matches("IMC", "IMC Trading"))

    def test_unrelated_company_rejected(self):
        self.assertFalse(company_matches("Booz Allen Hamilton", "Acme"))

    def test_alias_bytedance_tiktok(self):
        self.assertTrue(company_matches("TikTok", "ByteDance"))
        self.assertTrue(company_matches("TikTok Inc.", "ByteDance"))

    def test_none_and_nan_rejected(self):
        self.assertFalse(company_matches(None, "Acme"))
        self.assertFalse(company_matches(float("nan"), "Acme"))

    def test_empty_string_rejected(self):
        self.assertFalse(company_matches("", "Acme"))


class TestMatchesAnyTarget(unittest.TestCase):
    def setUp(self):
        self.targets = ["Acme", "Box", "X", "Nutanix", "IMC Trading"]

    def test_matches_and_returns_canonical_name(self):
        self.assertEqual(matches_any_target("Acme Corp", self.targets), "Acme")

    def test_returns_none_for_off_list_company(self):
        # Real example from production: Raytheon isn't a target, and
        # sharing letters with other targets must not cause a false match.
        self.assertIsNone(matches_any_target("Raytheon", self.targets))
        self.assertIsNone(matches_any_target("Booz Allen Hamilton", self.targets))

    def test_short_name_targets_dont_leak_into_unrelated_companies(self):
        self.assertIsNone(matches_any_target("Roblox", ["Box"]))
        self.assertIsNone(matches_any_target("Nutanix Inc.", ["X"]))

    def test_distinct_short_names_each_match_correctly(self):
        self.assertEqual(matches_any_target("Nutanix", self.targets), "Nutanix")
        self.assertEqual(matches_any_target("Box", self.targets), "Box")
        self.assertEqual(matches_any_target("X", self.targets), "X")


if __name__ == "__main__":
    unittest.main()
