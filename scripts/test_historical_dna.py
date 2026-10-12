#!/usr/bin/env python3
"""No-network QA for sanitized historical scoring and approved franchise continuity."""
import json
import math
import pathlib
import statistics
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=json.loads((ROOT/'reference/historical_regular_season_scores.json').read_text(encoding='utf8'))
IDENTITY=json.loads((ROOT/'reference/franchise_continuity.json').read_text(encoding='utf8'))
METRICS=json.loads((ROOT/'reference/metric_definitions.json').read_text(encoding='utf8'))
YEARS=(2014,2015,2016,2017,2021,2022,2023,2024,2025)
TOTALS={2014:17284.00,2015:17881.52,2016:17839.80,2017:17409.82,2021:19773.13,2022:19061.08,2023:16553.42,2024:16744.84,2025:16694.92}

def records(franchise):
    output=[]
    for season in SOURCE['seasons']:
        year=season['year']
        if str(year) not in IDENTITY['season_to_franchise']:continue  # Absent seasons are never inferred
        league_mean=statistics.mean(x for t in season['teams'] for x in t['scores'])
        for t in season['teams']:
            if IDENTITY['season_to_franchise'][str(year)][str(t['espn_team_id'])]!=franchise:
                continue
            mean=statistics.mean(t['scores'])
            output.append((year,mean/league_mean-1,statistics.pstdev(t['scores'])/mean))
    return sorted(output,reverse=True)

def fingerprint(franchise):
    observations=records(franchise)[:METRICS['historicalDna']['maxCompletedSeasons']]
    weights=METRICS['historicalDna']['completedSeasonWeights'][:len(observations)]
    divisor=sum(weights)
    return ([w/divisor for w in weights],
            sum(w*r[1] for w,r in zip(weights,observations))/divisor,
            sum(w*r[2] for w,r in zip(weights,observations))/divisor)

class TestHistoricalDna(unittest.TestCase):
    def test_complete_regular_season_and_reconciliation(self):
        self.assertEqual(SOURCE['league_id'],418244680)
        self.assertEqual(SOURCE['regular_season_weeks'],14)
        self.assertEqual([s['year'] for s in SOURCE['seasons']],list(YEARS))
        for s in SOURCE['seasons']:
            self.assertEqual(s['league_id'],791996 if s['year']<2021 else IDENTITY['league_ids_by_season'][str(s['year'])])
            if s['year']<2021:
                self.assertEqual(s['franchise_attribution'],'user_confirmed_account_reconciled_2014_2017')
            self.assertEqual(len(s['teams']),10)
            self.assertEqual({t['espn_team_id'] for t in s['teams']},set(range(1,11)))
            for t in s['teams']:
                self.assertEqual(len(t['scores']),14)
                self.assertTrue(all(isinstance(x,(int,float)) and math.isfinite(x) and x>=0 for x in t['scores']))
            self.assertAlmostEqual(sum(sum(t['scores']) for t in s['teams']),TOTALS[s['year']],places=2)
        self.assertEqual(sum(len(t['scores']) for s in SOURCE['seasons'] for t in s['teams']),1260)
    def test_no_current_or_postseason_in_historical_source(self):
        self.assertTrue(all(s['year']<METRICS['season'] for s in SOURCE['seasons']))
        self.assertEqual(SOURCE['regular_season_weeks'],14)
    def test_50_30_20_weights_and_all_time_separate(self):
        self.assertEqual(METRICS['historicalDna']['completedSeasonWeights'],[.5,.3,.2])
        self.assertEqual(METRICS['historicalDna']['maxCompletedSeasons'],3)
        w,relative,cv=fingerprint('franchise-01')
        self.assertEqual(w,[.5,.3,.2])
        self.assertAlmostEqual(relative,.08542,places=4)
        self.assertAlmostEqual(cv,.15062,places=4)
        all_time=statistics.mean(x[1] for x in records('franchise-01'))
        self.assertGreater(len(records('franchise-01')),5)
    def test_new_franchise_excludes_legacy_season(self):
        old=IDENTITY['season_to_franchise']['2023']['6']
        current=IDENTITY['season_to_franchise']['2026']['6']
        self.assertNotEqual(old,current)
        self.assertEqual([r[0] for r in records(current)],[2025,2024,2022,2021,2017,2016,2015,2014])
        self.assertEqual([r[0] for r in records(old)],[2023,2022,2021,2017,2016,2015,2014])
        w,relative,cv=fingerprint(current)
        self.assertEqual(w,[.5,.3,.2])
        self.assertAlmostEqual(relative,-.0104034,places=5)
        self.assertAlmostEqual(cv,.2189403,places=5)
        self.assertEqual([r[0] for r in records(current)[:3]],[2025,2024,2022])
        self.assertNotIn(2023,[r[0] for r in records(current)])
    def test_all_current_franchises_have_only_verified_history(self):
        for franchise in IDENTITY['season_to_franchise']['2026'].values():
            self.assertIn(len(records(franchise)),(3,7,8,9))
    def test_archived_punter_scoring_is_preserved_not_reinterpreted_as_roster_quality(self):
        archive=[s for s in SOURCE['seasons'] if s['year'] in (2021,2022)]
        self.assertEqual([s['year'] for s in archive],[2021,2022])
        self.assertTrue(all(s['scoring_environment']['starting_punter'] for s in archive))
        self.assertEqual(METRICS['lineup']['weightedPossible'],8)
        self.assertFalse(any('rosterAnalysis' in s or 'starterWorthyRate' in s for s in archive))

    def test_archived_owners_follow_verified_franchise_and_returning_manager(self):
        old=IDENTITY['season_to_franchise']
        self.assertEqual(old['2021']['1'],old['2022']['1'])
        self.assertEqual(old['2022']['1'],old['2024']['6'])  # Returning franchise
        self.assertNotEqual(old['2022']['1'],old['2023']['6'])  # Different owner of 2023 slot
        self.assertEqual(old['2022']['2'],old['2023']['6'])
        self.assertNotEqual(old['2023']['5'],old['2022']['1'])  # New participant in 2023

    def test_no_private_owner_fields(self):
        raw=json.dumps(SOURCE).lower()
        for forbidden in ('owner_name','manager_name','espn_s2','espn_swid','owner_id','manager_id'):
            self.assertNotIn(forbidden,raw)

if __name__=='__main__':
    unittest.main()
