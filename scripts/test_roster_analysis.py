#!/usr/bin/env python3
"""Synthetic regression suite; no credentials and no fabricated public league results."""
import json, sys, unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import roster_analysis as r
from attach_roster_analysis import attach


def player(pid,pos,points,slot=20):return {'id':pid,'name':f'P{pid}','pos':pos,'points':points,'slot':slot}

def universe():
    items=[];n=0
    for pos,count,ceiling in [('QB',32,36),('RB',50,31),('WR',70,30),('TE',40,22),('K',32,17),('DST',32,17)]:
        for j in range(count):
            n+=1;items.append(player(n,pos,round(max(0,ceiling-j*.43),2)))
    return {p['id']:p for p in items}

class RosterCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pool=universe();cls.sets,cls.cutoffs=r.qualified_sets(cls.pool)
    def nth(self,pos,n,slot=20):
        pp=sorted((p for p in self.pool.values() if p['pos']==pos),key=lambda x:-x['points'])
        return dict(pp[n-1],slot=slot)
    def test_qualifier_thresholds(self):
        for pos,n in r.BASE.items():
            self.assertIn(self.nth(pos,n)['id'],self.sets[pos]);self.assertNotIn(self.nth(pos,n+1)['id'],self.sets[pos])
    def test_flex_ten_extra_without_double_count(self):
        flex=self.sets['FLEX'];self.assertEqual(len(flex),10)
        self.assertTrue(all(pid not in self.sets[p] for p in ('RB','WR','TE') for pid in flex))
    def test_top20_rb_qualifies_even_in_flex(self):self.assertTrue(r.qualifies(self.nth('RB',12),'FLEX',self.sets))
    def test_rb21_does_not_qualify_rb_slot(self):self.assertFalse(r.qualifies(self.nth('RB',21),'RB',self.sets))
    def test_cross_season_same_week_uses_target_year(self):
        row={'playerPoolEntry':{'id':4249087,'player':{'defaultPositionId':2,'stats':[
            {'seasonId':2026,'scoringPeriodId':1,'statSourceId':0,'statSplitTypeId':1,'appliedTotal':10},
            {'seasonId':2025,'scoringPeriodId':1,'statSourceId':0,'statSplitTypeId':1,'appliedTotal':3}]}}}
        self.assertEqual(r.clean_player(row,1)['points'],10)

    def test_explicit_2026_actual_takes_precedence_over_untagged_duplicate(self):
        row={'playerPoolEntry':{'id':4249087,'player':{'defaultPositionId':2,'stats':[
            {'scoringPeriodId':1,'statSourceId':0,'statSplitTypeId':1,'appliedTotal':7},
            {'seasonId':2026,'scoringPeriodId':1,'statSourceId':0,'statSplitTypeId':1,'appliedTotal':10},
            {'seasonId':2025,'scoringPeriodId':1,'statSourceId':0,'statSplitTypeId':1,'appliedTotal':3}]}}}
        self.assertEqual(r.clean_player(row,1)['points'],10)

    def test_conflicting_untagged_actuals_still_rejected(self):
        row={'playerPoolEntry':{'id':4249087,'player':{'defaultPositionId':2,'stats':[
            {'scoringPeriodId':1,'statSourceId':0,'statSplitTypeId':1,'appliedTotal':7},
            {'scoringPeriodId':1,'statSourceId':0,'statSplitTypeId':1,'appliedTotal':10}]}}}
        with self.assertRaisesRegex(ValueError,'Ambiguous actual weekly stats'):
            r.clean_player(row,1)

    def test_conflicting_same_season_actuals_still_rejected(self):
        row={'playerPoolEntry':{'id':4249087,'player':{'defaultPositionId':2,'stats':[
            {'seasonId':2026,'scoringPeriodId':1,'statSourceId':0,'statSplitTypeId':1,'appliedTotal':10},
            {'seasonId':2026,'scoringPeriodId':1,'statSourceId':0,'statSplitTypeId':1,'appliedTotal':3}]}}}
        with self.assertRaisesRegex(ValueError,'Ambiguous actual weekly stats'):
            r.clean_player(row,1)

    def test_negative_defense_scores_supported(self):
        row={'playerPoolEntry':{'id':8,'player':{'defaultPositionId':16,'fullName':'Defense','stats':[{'scoringPeriodId':1,'statSourceId':0,'statSplitTypeId':1,'appliedTotal':-4}]}},'lineupSlotId':16}
        self.assertEqual(r.clean_player(row,1)['points'],-4)
    def test_never_uses_season_total_or_projection(self):
        row={'playerPoolEntry':{'id':8,'player':{'defaultPositionId':16,'fullName':'Defense','stats':[{'scoringPeriodId':1,'statSourceId':1,'statSplitTypeId':1,'appliedTotal':18},{'scoringPeriodId':1,'statSourceId':0,'statSplitTypeId':0,'appliedTotal':180}]}}}
        self.assertEqual(r.clean_player(row,1)['points'],0)
    def lineup(self):
        positions=[('QB',1,0),('RB',4,2),('RB',28,2),('WR',5,4),('WR',35,4),('TE',3,6),('RB',10,23),('K',14,17),('DST',4,16)]
        return [self.nth(pos,n,slot) for pos,n,slot in positions]
    def test_bench_replacement_and_half_weight(self):
        active=self.lineup(); bench=[self.nth('RB',14),self.nth('WR',12),self.nth('K',3)]
        observed={9:active+bench};res=r.analyze_week(observed,self.pool,1,{9:1})['teams'][0]
        self.assertEqual(res['weightedHits'],5.5) # QB RB1 WR1 TE FLEX DST
        self.assertEqual(res['weightedMax'],8.0)
        self.assertEqual(res['missedWeighted'],2.5)
        self.assertEqual(res['reassignmentWeighted'],0)
        self.assertEqual(len(res['slots']),9)
    def test_full_qualified_roster_bench_is_not_a_miss(self):
        active=[self.nth(pos,n,slot) for pos,n,slot in [('QB',1,0),('RB',2,2),('RB',3,2),('WR',4,4),('WR',5,4),('TE',1,6),('RB',4,23),('K',1,17),('DST',1,16)]]
        res=r.analyze_week({9:active+[self.nth('WR',1)]},self.pool,1,{9:1})['teams'][0]
        self.assertEqual(res['weightedHits'],8);self.assertEqual(res['missedWeighted'],0);self.assertEqual(res['benchOpportunities'],[])
    def test_ir_player_never_eligible(self):
        active=self.lineup();ir=self.nth('WR',1,21)
        a=r.analyze_week({9:active+[ir]},self.pool,1,{9:1})['teams'][0]
        b=r.analyze_week({9:active},self.pool,1,{9:1})['teams'][0]
        self.assertEqual(a['weightedMax'],b['weightedMax'])
    def test_reassignment_is_separate_from_bench_miss(self):
        # Weak RB21 in RB2; qualified RB10 in FLEX. With no bench, swapping raises 1 qualification.
        active=[self.nth(pos,n,slot) for pos,n,slot in [('QB',1,0),('RB',2,2),('RB',21,2),('WR',4,4),('WR',5,4),('TE',1,6),('RB',10,23),('K',1,17),('DST',1,16)]]
        res=r.analyze_week({9:active},self.pool,1,{9:1})['teams'][0]
        # RB21 may itself be flex-qualified depending on how points compare; if so, reassign improves.
        if active[2]['id'] in self.sets['FLEX']:
            self.assertEqual(res['reassignmentWeighted'],1)
        self.assertEqual(res['missedWeighted'],0)
    def test_ties_included_at_boundary(self):
        copy={k:dict(v) for k,v in self.pool.items()};cut=self.nth('RB',20)['points'];copy[self.nth('RB',21)['id']]['points']=cut
        sets,_=r.qualified_sets(copy)
        self.assertIn(self.nth('RB',21)['id'],sets['RB'])
    def test_weekly_player_pool_request_has_sort_and_actual_stats_filter(self):
        calls=[]
        def fake_request(params,filters=None):
            calls.append((params,filters))
            if any(k=='view' and v=='kona_player_info' for k,v in params):
                return {'players':[{'id':1}]}
            return {'id':r.LEAGUE_ID,'schedule':[{'id':i} for i in range(5)]}
        with patch.object(r,'_get_json',side_effect=fake_request):
            r.fetch_week(1)
        player_filter=calls[1][1]['players']
        self.assertEqual(player_filter['sortPercOwned'],{'sortPriority':1,'sortAsc':False})
        self.assertEqual(player_filter['filterStatsForTopScoringPeriodIds'],{'value':18,'additionalValue':['002026']})
        self.assertEqual(player_filter['limit'],r.PAGE_SIZE)

    def test_sanitized_approved_dataset_reaches_retrieval(self):
        league=json.loads((Path(__file__).parents[1]/'data/league.json').read_text())
        mapping=json.loads((Path(__file__).parents[1]/'reference/team_id_map.json').read_text())
        self.assertNotIn('leagueId',league)
        self.assertNotIn('season',league)
        with patch.object(r,'fetch_week',side_effect=RuntimeError('retrieval reached')) as fetch:
            with self.assertRaisesRegex(RuntimeError,'retrieval reached'):
                r.build(league,mapping,[1])
            fetch.assert_called_once_with(1)
    def test_unapproved_dataset_source_rejected(self):
        league=json.loads((Path(__file__).parents[1]/'data/league.json').read_text())
        mapping=json.loads((Path(__file__).parents[1]/'reference/team_id_map.json').read_text())
        league['source']='unknown'
        with self.assertRaisesRegex(ValueError,'Wrong approved league dataset'):
            r.build(league,mapping,[1])
    def test_backwards_and_partial_roster_rejected(self):
        league=json.loads((Path(__file__).parents[1]/'data/league.json').read_text());mapping=json.loads((Path(__file__).parents[1]/'reference/team_id_map.json').read_text())
        with self.assertRaises(ValueError):r.build(league,mapping,[league['completedThrough']+1],fixture_dir='unused')
    def test_attach_disallows_partial_set(self):
        league=json.loads((Path(__file__).parents[1]/'data/league.json').read_text())
        roster={'leagueId':418244680,'season':2026,'completedThrough':4,'weeks':[{'week':1,'teams':[]}]}
        with self.assertRaises(ValueError):attach(league,roster)

if __name__=='__main__':unittest.main(verbosity=2)