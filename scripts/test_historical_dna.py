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
YEARS=(2023,2024,2025)
TOTALS={2023:16553.42,2024:16744.84,2025:16694.92}

def records(franchise):
    output=[]
    for season in SOURCE['seasons']:
        year=season['year']
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
            self.assertEqual(len(s['teams']),10)
            self.assertEqual({t['espn_team_id'] for t in s['teams']},set(range(1,11)))
            for t in s['teams']:
                self.assertEqual(len(t['scores']),14)
                self.assertTrue(all(isinstance(x,(int,float)) and math.isfinite(x) and x>=0 for x in t['scores']))
            self.assertAlmostEqual(sum(sum(t['scores']) for t in s['teams']),TOTALS[s['year']],places=2)
        self.assertEqual(sum(len(t['scores']) for s in SOURCE['seasons'] for t in s['teams']),420)
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
        self.assertAlmostEqual(all_time,.11110,places=4)
    def test_new_franchise_excludes_legacy_season(self):
        old=IDENTITY['season_to_franchise']['2023']['6']
        current=IDENTITY['season_to_franchise']['2026']['6']
        self.assertNotEqual(old,current)
        self.assertEqual([r[0] for r in records(current)],[2025,2024])
        self.assertEqual([r[0] for r in records(old)],[2023])
        w,relative,cv=fingerprint(current)
        self.assertEqual(w,[.625,.375])
        self.assertAlmostEqual(relative,.011,places=3)
        self.assertAlmostEqual(cv,.215,places=3)
    def test_all_current_franchises_have_only_verified_history(self):
        for franchise in IDENTITY['season_to_franchise']['2026'].values():
            self.assertIn(len(records(franchise)),(2,3))
    def test_no_private_owner_fields(self):
        raw=json.dumps(SOURCE).lower()
        for forbidden in ('owner_name','manager_name','espn_s2','espn_swid','owner_id','manager_id'):
            self.assertNotIn(forbidden,raw)

if __name__=='__main__':
    unittest.main()
