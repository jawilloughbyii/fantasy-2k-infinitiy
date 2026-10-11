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
 assert.ok(view.includes('roster-action') && view.includes('Roster ceiling'),'Overview must lead with usable lineup data');
 assert.ok(view.includes('W4 · BIGGEST SCHEDULE BOOST') && view.includes('extra wins in Week 4'));
 assert.ok(!view.includes('Points vs ESPN'));
 assert.equal(node('weekStatus').textContent,'Early season · 4 weeks');
 function tab(tab){
  events.click({target:{closest(selector){return selector==='[data-tab]'?{dataset:{tab}}:null}}});
  return node('view').innerHTML;
 }
 view=tab('performance');
 assert.ok(view.includes('Volatile underdogs'),'Default selected team uses canonical quadrant');
 assert.ok(!view.includes('Inconsistent underdog'));
 assert.ok(!view.includes('Scoring versus recorded ESPN projections'));
 assert.ok(!view.includes('Season versus recent scoring identity'),'Four-week recent DNA must be gated');
 assert.ok(!view.includes('Six-week momentum'),'Four-week momentum must be gated');
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
 console.log('Dashboard regression checks passed: paired snapshots, 40 rosters, canonical quadrants, timing gates, luck windows and active pages.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
