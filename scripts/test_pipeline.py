#!/usr/bin/env python3
"""No-network regression checks for the public ESPN report builder."""
import copy
import json
import pathlib
import unittest
import build_site_data as site
import refresh

ROOT=pathlib.Path(__file__).resolve().parents[1]
class TestPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads((ROOT/'reference/synthetic_test_fixture.json').read_text())
        cls.baseline=json.loads((ROOT/'reference/validated_weeks_1_4.json').read_text())
        cls.base=site.embed(ROOT/'index.html')
    def report(self,fixture):
        teams, matches=refresh.extract(fixture)
        validation=refresh.validate(teams,matches,self.baseline)
        return {'season':2026,'league_id':418244680,'generated_at_utc':'2026-10-10T00:00:00+00:00','validation':validation,'safe_teams':teams,'matchups':matches,'current_matchup_period':fixture.get('status',{}).get('currentMatchupPeriod')}
    def test_original_baseline(self):
        d=site.build(self.report(self.fixture),self.base)
        self.assertEqual(d['completedThrough'],4)
        self.assertEqual(sum(len(t['weeks']) for t in d['teams']),40)
        self.assertEqual(len(d['dnaHistory']),4)
        self.assertTrue(all(t['projWeeks']==4 for t in d['teams']))
        self.assertAlmostEqual(d['leagueAveragePf'],120.92,places=1)
        self.assertEqual(d['simulationRuns'],100000)
    def test_shared_quadrants_match_generated_history(self):
        d=site.build(self.report(self.fixture),self.base)
        expected=site.METRICS['scoring']['quadrants']
        self.assertEqual(len(expected),4)
        categories={x['id']:x['category'] for x in d['dnaHistory'][-1]['teams']}
        self.assertEqual(categories[4],'Steady, lower-output')
        self.assertEqual(categories[5],'Steady, lower-output')
        self.assertTrue(set(categories.values()).issubset(set(expected)))
        self.assertNotIn('rosterAnalysis',d,'Refreshed scoring must not silently carry stale finalized rosters')
        for team in d['teams']:
            self.assertNotIn('rankLuckPct',team)
            self.assertNotIn('winLuckPct',team)
            self.assertNotIn('luckpp',team)
    def test_active_week_excluded_even_with_live_points(self):
        x=copy.deepcopy(self.fixture);x['status']={'currentMatchupPeriod':5}
        # Current week only has partial scores, still must be excluded
        x['schedule'].append({'id':21,'matchupPeriodId':5,'home':{'teamId':9,'totalPoints':12},'away':{'teamId':2,'totalPoints':9},'winner':'UNDECIDED'})
        d=site.build(self.report(x),self.base)
        self.assertEqual(d['completedThrough'],4)
    def test_missing_final_matchup_fails_closed(self):
        x=copy.deepcopy(self.fixture);x['status']={'currentMatchupPeriod':6}
        with self.assertRaisesRegex(ValueError,'Week 5'):
            site.build(self.report(x),self.base)
    def test_score_tampering_is_caught(self):
        x=copy.deepcopy(self.fixture);x['schedule'][0]['home']['totalPoints']+=2
        r=self.report(x)
        self.assertFalse(r['validation']['passed'])
        with self.assertRaisesRegex(ValueError,'baseline validation'):
            site.build(r,self.base)
    def test_no_sensitive_fields(self):
        d=site.build(self.report(self.fixture),self.base)
        out=json.dumps(d).lower()
        for keyword in ('espn_s2','espn_swid','espn_cookie','owner_name','manager_name','first_name','last_name'):
            self.assertNotIn(keyword,out)
if __name__=='__main__':unittest.main()
