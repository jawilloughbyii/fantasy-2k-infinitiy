#!/usr/bin/env python3
"""Offline fail-closed reconciliation of 2014–2017 merged historical ESPN data.

No historic ESPN team ID is treated as the same owner across years.
2015 championship advancement discrepancy stays unresolved.
"""
import json
import pathlib
import unittest
from collections import defaultdict

ROOT=pathlib.Path(__file__).resolve().parents[1]
SCORES=json.loads((ROOT/'reference/historical_regular_season_scores.json').read_text())
DRAFTS=json.loads((ROOT/'reference/historical_legacy_draft_picks_2014_2017.json').read_text())
FRANCHISE=json.loads((ROOT/'reference/franchise_continuity.json').read_text())
CHAMPS=json.loads((ROOT/'reference/championship_history.json').read_text())
EXPECTED={2014:17284.00,2015:17881.52,2016:17839.80,2017:17409.82}
LEGACY_ID=791996

def archive(year):
    return json.loads((ROOT/f'research/espn-791996-2014-2017/season_{year}.json').read_text())

class HistoricalLegacyValidation(unittest.TestCase):
    def test_score_and_matchup_reconciliation(self):
        self.assertEqual([s['year'] for s in SCORES['seasons']],
                         [2014,2015,2016,2017,2021,2022,2023,2024,2025])
        self.assertEqual(SCORES['regular_season_weeks'],14)
        for year,total in EXPECTED.items():
            with self.subTest(year=year):
                a=archive(year)
                s=next(s for s in SCORES['seasons'] if s['year']==year)
                self.assertEqual((a['league_id'],s['league_id']),(LEGACY_ID,LEGACY_ID))
                self.assertEqual(s['franchise_attribution'],'user_confirmed_account_reconciled_2014_2017')
                self.assertEqual(len(s['teams']),10)
                regular=[m for m in a['matchups'] if type(m['week']) is int and m['week']<=14]
                self.assertEqual(len(regular),70)
                observations=defaultdict(dict)
                for match in regular:
                    w=match['week']
                    self.assertEqual(len(match['sides']),2)
                    self.assertIn(match['winner'],('HOME','AWAY','TIE'))
                    for side in match['sides']:
                        team=side['espn_team_id']
                        self.assertNotIn(team,observations[w])
                        observations[w][team]=side['points']
                self.assertEqual(set(observations),set(range(1,15)))
                self.assertTrue(all(len(points)==10 for points in observations.values()))
                self.assertEqual({t['espn_team_id'] for t in s['teams']},set(range(1,11)))
                for t in s['teams']:
                    tid=t['espn_team_id']
                    self.assertEqual(t['scores'],[observations[w][tid] for w in range(1,15)])
                    self.assertEqual(len(t['scores']),14)
                    self.assertEqual(t['name'],next(z['display_name'] for z in a['teams'] if z['espn_team_id']==tid))
                self.assertAlmostEqual(sum(sum(t['scores']) for t in s['teams']),total,places=2)
        # Original five years must retain their approved scores and league IDs.
        self.assertEqual([(s['year'],s['league_id']) for s in SCORES['seasons'] if s['year']>=2021],
                         [(2021,1493036707),(2022,1493036707),(2023,418244680),
                          (2024,418244680),(2025,418244680)])

    def test_draft_exact_source_and_unmapped_ownership(self):
        self.assertEqual(DRAFTS['status'],'verified_original_year_player_metadata_complete')
        self.assertEqual(DRAFTS['coverage']['pick_count'],680)
        self.assertEqual(DRAFTS['coverage']['named_picks'],680)
        self.assertEqual(DRAFTS['coverage']['positioned_picks'],680)
        self.assertEqual([s['year'] for s in DRAFTS['seasons']],list(EXPECTED))
        for d in DRAFTS['seasons']:
            a=archive(d['year'])
            self.assertEqual(d['league_id'],LEGACY_ID)
            self.assertEqual((len(d['picks']),d['total_picks'],d['rounds']),(170,170,17))
            self.assertEqual([p['overall'] for p in d['picks']],list(range(1,171)))
            self.assertEqual(len({p['player_id'] for p in d['picks']}),170)
            self.assertEqual({p['espn_team_id'] for p in d['picks']},set(range(1,11)))
            self.assertEqual({t['franchise_id'] for t in d['teams']},{FRANCHISE['season_to_franchise'][str(d['year'])][str(t['espn_team_id'])] for t in d['teams']})
            src={p['overallPickNumber']:p for p in a['draft']['picks']}
            for p in d['picks']:
                q=src[p['overall']]
                self.assertEqual((p['round'],p['round_pick'],p['espn_team_id'],p['player_id']),
                                 (q['roundId'],q['roundPickNumber'],q['teamId'],q['playerId']))
                self.assertEqual(p['franchise_id'],FRANCHISE['season_to_franchise'][str(d['year'])][str(p['espn_team_id'])])
                self.assertTrue(isinstance(p['player_name'],str) and p['player_name'].strip())
                self.assertIn(p['position'],('QB','RB','WR','TE','K','D/ST','P'))
                self.assertEqual(p['player_metadata_source'],'ESPN_season_players_wl_exact_original_draft_id')

    def test_playoff_titles_carefully_separated(self):
        self.assertEqual({c['season'] for c in CHAMPS['champions']},set(range(2021,2026)))
        self.assertTrue(all(str(y) in FRANCHISE['season_to_franchise'] for y in EXPECTED))
        for year in EXPECTED:
            a=archive(year)
            s=next(s for s in SCORES['seasons'] if s['year']==year)
            self.assertEqual(s['postseason']['status'],a['postseason']['status'])
            self.assertEqual(s['postseason']['winner_espn_team_id'],
                             a['postseason']['winner_record']['espn_team_id'])
            self.assertEqual(len(s['postseason']['winners_bracket_games']),3)
            self.assertEqual(s['postseason']['bracket_validated'],year!=2015)
        self.assertEqual(next(s for s in SCORES['seasons'] if s['year']==2015)['postseason']['status'],
                         'source_final_record_only_advancement_unresolved')

    def test_no_leaked_identity_or_live_data_mutation(self):
        assert DRAFTS['coverage']['team_seasons']==40
        raw=json.dumps({'old_scores':[s for s in SCORES['seasons'] if s['year']<2021],'drafts':DRAFTS}).lower()
        for word in ('"owner_name"','"manager_name"','"memberid"','"espn_s2"','"espn_swid"','"cookie"'):
            self.assertNotIn(word,raw)

if __name__=='__main__':
    unittest.main()
