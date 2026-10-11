#!/usr/bin/env python3
"""No-network regression tests for verified historical franchise boundaries."""
import copy
import unittest
import franchise_identity as fid


class TestFranchiseIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = fid.load_mapping()

    def test_verified_2023_through_2026_coverage(self):
        self.assertEqual(set(self.reference['season_to_franchise']), {'2023', '2024', '2025', '2026'})
        self.assertEqual(len({f for season in self.reference['season_to_franchise'].values() for f in season.values()}), 11)

    def test_team_six_transition(self):
        f23 = fid.franchise_for(2023, 6, self.reference)
        f24 = fid.franchise_for(2024, 6, self.reference)
        self.assertNotEqual(f23, f24)
        self.assertEqual(f24, fid.franchise_for(2025, 6, self.reference))
        self.assertEqual(f24, fid.franchise_for(2026, 6, self.reference))

    def test_other_slots_are_continuous(self):
        for tid in range(1, 11):
            if tid == 6:
                continue
            self.assertEqual(len({fid.franchise_for(year, tid, self.reference)
                                  for year in range(2023, 2027)}), 1)

    def test_unmapped_year_and_id_fail_closed(self):
        for season, team_id in ((2022, 6), (2027, 6), (2025, 11)):
            with self.assertRaisesRegex(ValueError, 'Unverified franchise key'):
                fid.franchise_for(season, team_id, self.reference)

    def test_undeclared_ownership_change_fails(self):
        data = copy.deepcopy(self.reference)
        data['season_to_franchise']['2025']['3'] = 'unreviewed-new-franchise'
        with self.assertRaisesRegex(ValueError, 'Undocumented franchise change'):
            fid.validate_mapping(data)

    def test_split_cannot_be_silently_undone(self):
        data = copy.deepcopy(self.reference)
        data['season_to_franchise']['2023']['6'] = data['season_to_franchise']['2024']['6']
        with self.assertRaises(ValueError):
            fid.validate_mapping(data)

    def test_no_duplicate_franchise_slots(self):
        data = copy.deepcopy(self.reference)
        data['season_to_franchise']['2024']['7'] = data['season_to_franchise']['2024']['8']
        with self.assertRaisesRegex(ValueError, 'two ESPN slots'):
            fid.validate_mapping(data)

    def test_no_sensitive_identity_fields(self):
        data = copy.deepcopy(self.reference)
        data['owner_id'] = 'must-not-be-stored'
        with self.assertRaisesRegex(ValueError, 'Sensitive identity'):
            fid.validate_mapping(data)


if __name__ == '__main__':
    unittest.main()
