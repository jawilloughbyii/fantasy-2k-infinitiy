#!/usr/bin/env node
// Offline smoke and regression checks. Never requires ESPN credentials.
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ROOT=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');
const data=JSON.parse(fs.readFileSync(path.join(ROOT,'data/league.json'),'utf8'));
const definitions=JSON.parse(fs.readFileSync(path.join(ROOT,'reference/metric_definitions.json'),'utf8'));
function embedded(id){
 const begin='<script id="'+id+'" type="application/json">';
 const a=html.indexOf(begin),b=html.indexOf('</script>',a+begin.length);
 assert.ok(a>=0 && b>a,'Missing embedded '+id);
 return JSON.parse(html.slice(a+begin.length,b));
}
assert.deepStrictEqual(embedded('fantasydata'),data,'External JSON and embedded fallback must match');
assert.deepStrictEqual(embedded('metricdefs'),definitions,'HTML definitions must come from one canonical file');
assert.equal(data.teams.length,10);
assert.equal(data.completedThrough,4);
assert.equal(data.rosterAnalysis.weeks.length,4);
const possible=definitions.lineup.weightedPossible;
for(const w of data.rosterAnalysis.weeks){
 assert.equal(w.teams.length,10,'10 finalized rosters per week');
 for(const x of w.teams){
  assert.ok(x.weightedHits<=x.weightedMax && x.weightedMax<=possible);
  assert.ok(Math.abs((x.weightedMax-x.weightedHits)-(x.missedWeighted+x.reassignmentWeighted))<.001);
  assert.equal(x.slots.length,9);
 }
}
const mean=a=>a.reduce((n,v)=>n+v,0)/a.length;
function category(t,n=data.completedThrough){
 const scores=t.weeks.slice(0,n).map(w=>w.pf),av=mean(scores);
 const sd=Math.sqrt(mean(scores.map(x=>(x-av)**2)));
 const league=mean(data.teams.map(z=>mean(z.weeks.slice(0,n).map(w=>w.pf))));
 return definitions.scoring.quadrants[(av>=league?1:0)+(sd/av>definitions.scoring.quadrantCvBoundary?0:2)];
}
for(const t of data.teams){
 const historical=data.dnaHistory.at(-1).teams.find(x=>x.id===t.id);
 assert.equal(historical.category,category(t),'HTML and approved history quadrant must match for '+t.name);
}
assert.equal(category(data.teams.find(t=>t.id===4)),'Steady, lower-output');
assert.equal(category(data.teams.find(t=>t.id===5)),'Steady, lower-output');
const haily=data.teams.find(t=>t.id===7),cats=data.teams.find(t=>t.id===6);
assert.ok(haily.weeks[3].weekLuck>cats.weeks[3].weekLuck);
assert.ok(cats.luck>haily.luck,'Weekly talking point and season luck are different time windows');
assert.ok(!html.includes('function badBeatReport(){'),'Premature Bad Beats section should be removed');
assert.ok(!html.includes('function leagueOverview(){'),'Overview must not start with league-only KPIs');
assert.ok(!html.includes('function oldPerf(){'),'Unverified projection section should be removed');
assert.ok(html.includes('const RANK_COLORS=METRICS.rankColors;'));
// Exercise actual page rendering with a minimal document, without browser deps or network.
const elements=new Map(),events={};
function node(id){
 if(!elements.has(id))elements.set(id,{
  id,innerHTML:'',textContent:'',value:'',title:'',listeners:{},
  classList:{toggle(){}},
  addEventListener(name,handler){this.listeners[name]=handler}
 });
 return elements.get(id);
}
const doc={
 getElementById(id){const el=node(id);if(id==='fantasydata')el.textContent=JSON.stringify(data);if(id==='metricdefs')el.textContent=JSON.stringify(definitions);return el;},querySelectorAll:()=>[],
 addEventListener(name,handler){events[name]=handler}
};
const fetch=async()=>({ok:true,json:async()=>data});
const script=html.match(/<script>\s*([\s\S]*?)<\/script>/);
assert.ok(script,'Dashboard JavaScript missing');
vm.runInNewContext(script[1],{document:doc,window:{scrollTo(){}},fetch,console}, {timeout:5000});
async function main(){
 for(let i=0;i<8;i++)await Promise.resolve();
 let view=node('view').innerHTML;
 assert.ok(view.includes('League standings & scoring rank'));
 assert.ok(view.includes('power-desktop') && view.includes('power-table'),'Desktop must use compact data table');
 assert.ok(view.includes('power-mobile-item') && view.includes('power-mobile-toggle'),'Mobile must use compact expandable rows');
 assert.ok(view.includes('<th>Team DNA</th>') && view.includes('<th class="num">CV</th>'),'Desktop table needs DNA and CV columns');
 assert.ok(view.includes('Steady, lower-output') && view.includes('Reliable contenders'),'Use canonical four-quadrant DNA labels');
 assert.equal((view.match(/<tr class="[^"]*" data-select="/g)||[]).length,10,'Desktop must show ten teams');
 assert.equal((view.match(/class="power-mobile-item /g)||[]).length,10,'Mobile must show ten teams');
 assert.equal((view.match(/class="power-mobile-detail"/g)||[]).length,0,'Mobile details should start collapsed');
 assert.ok(!view.includes('mini-spark'),'Large sparkline grid must be removed from standings');
 assert.ok(view.includes('All-play') && view.includes('Extra wins') && view.includes('Form'),'Desktop must retain competitive metrics');
 events.click({target:{closest(selector){return selector==='[data-expand-standing]'?{dataset:{expandStanding:'6'}}:null}}});
 view=node('view').innerHTML;
 assert.ok(view.includes('id="standing-detail-6"') && view.includes('View The Domestic House Cats'),'House Cats expansion shows the detail action');
 assert.ok(view.includes('Volatility (CV)') && view.includes('All-play') && view.includes('Form · PF/week'),'Expanded mobile row exposes hidden fields');
 assert.ok(view.includes('9.8%') && view.includes('Reliable contenders') && view.includes('24–12'),'Expanded mobile row shows CV, DNA and all-play');
 assert.equal((view.match(/class="power-mobile-detail"/g)||[]).length,1,'Only one expanded mobile row at a time');
 events.click({target:{closest(selector){return selector==='[data-expand-standing]'?{dataset:{expandStanding:'6'}}:null}}});
 view=node('view').innerHTML;
 assert.equal((view.match(/class="power-mobile-detail"/g)||[]).length,0,'Clicking expanded mobile row collapses it');
 events.click({target:{closest(selector){return selector==='[data-select]'?{dataset:{select:'6'}}:null}}});
 view=node('view').innerHTML;
 assert.ok(view.includes('4–0') && view.includes('Your bench'),'Mobile detail View Team updates selected-team profile');
 // Return to the default selected team for the remaining regression checks.
 node('teamSelect').listeners.change({target:{value:'3'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('League avg PF') && view.includes('League form'),'Standings require a league benchmark');
 assert.ok(view.includes('23–13') && !view.includes('23.0–13.0'),'All-play must suppress unnecessary decimals');
 assert.ok(view.includes('+50.7') && view.includes('League form'),'Early raw trend must be available at Week 4');
 assert.ok(view.includes('League 45.2%') && view.includes('League 62.3%') && view.includes('League 72.6%'),'All three roster percentages require league comparisons');
 assert.ok(view.includes('most missed'),'Bench opportunity needs league rank context');
 assert.ok(view.includes('roster-action') && view.includes('Roster ceiling'),'Overview must lead with usable lineup data');
 assert.ok(!view.includes('Week 4 talking points') && !html.includes('function weekHeadlines(){'),'Talking points must be removed');
 assert.ok(!view.includes('Avg extra wins'),'Zero-sum extra-wins average is not useful');
 assert.ok(view.includes('League avg PF') && view.includes('Extra wins'),'League context remains alongside standings');
 assert.ok(!view.includes('Points vs ESPN'));
 assert.equal(node('weekStatus').textContent,'Early season · 4 weeks');
 function tab(tab){
  events.click({target:{closest(selector){return selector==='[data-tab]'?{dataset:{tab}}:null}}});
  return node('view').innerHTML;
 }
 view=tab('cards');
 assert.ok(view.includes('tc-report') && view.includes('tc-primary-grid') && view.includes('tc-stats') && view.includes('tc-trends'),'Team Cards should have screenshot-ready report structure');
 assert.ok(view.includes('TEAM DNA') && view.includes('EXTRA WINS') && view.includes('STARTER-WORTHY'),'Team Card headline metrics missing');
 assert.ok(view.includes('viewBox="0 0 24 24"') && view.includes('<circle cx="9.15"'),'Use minimalist SVG icons including the four-leaf clover');
 assert.equal((view.match(/class="tc-stat"/g)||[]).length,6,'Exactly six benchmarked tiles');
 assert.ok(view.includes('VS LEAGUE AVERAGE') && view.includes('Midpoint: 18–18'),'All-play must use the natural league midpoint');
 assert.ok(view.includes('League avg:') && view.includes('BENCH MISS') && view.includes('UNAVOIDABLE'),'Lineup opportunity metrics need comparable league per-week benchmarks');
 assert.ok(view.includes('LINEUP SWR') && view.includes('CUMUL. LUCK'),'Three tiny chart labels required');
 assert.ok(view.includes('2026 · WEEKS 1–4') && view.includes('Israeli Nutonyaboob'),'Card uses approved selected team and completed weeks');
 assert.ok(!view.includes('0–0 · placeholder'),'No invented score or placeholders');
 events.click({target:{closest(selector){return selector==='[data-card-step]'?{dataset:{cardStep:'1'}}:null}}});
 view=node('view').innerHTML;
 assert.ok(view.includes('Quattro Padres') && view.includes('PF RANK #'),'Card next/previous control follows points-scored order');
 node('teamSelect').listeners.change({target:{value:'3'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('Israeli Nutonyaboob'),'Shared selected-team dropdown also selects report card');
 view=tab('performance');
 assert.ok(view.includes('Volatile underdogs'),'Default selected team uses canonical quadrant');
 assert.ok(!view.includes('Inconsistent underdog'));
 assert.ok(!view.includes('Scoring versus recorded ESPN projections'));
 assert.ok(!view.includes('Season versus recent scoring identity'),'Four-week recent DNA must be gated');
 assert.ok(view.includes('Recent scoring trend') && view.includes('+50.7 PF/week'),'Four-week momentum must compare latest two against prior two');
 assert.ok(!view.includes('Last 3 weeks'),'Trailing lineup average must be gated');
 assert.ok(view.includes('/ 8 quality points') && view.includes('K/DST half-weighted'));
 node('teamSelect').listeners.change({target:{value:'4'}});
 assert.ok(node('view').innerHTML.includes('Steady, lower-output'),'Golden Ponies map/identity must agree');
 node('teamSelect').listeners.change({target:{value:'5'}});
 assert.ok(node('view').innerHTML.includes('Steady, lower-output'),'Quattro Padres map/identity must agree');
 view=tab('luck');
 assert.ok(view.includes('Extra wins are the headline.'));
 assert.ok(!view.includes('Bad beats'));
 view=tab('divisions');
 assert.ok(view.includes('darkest = 1st') && !view.includes('out of 100'),'What-if must not display competing fortune score');
 console.log('Dashboard regression checks passed: paired snapshots, 40 rosters, compact desktop table, mobile expand/collapse and selection, DNA, CV, benchmarks and active pages.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
