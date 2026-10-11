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
const continuity=JSON.parse(fs.readFileSync(path.join(ROOT,'reference/franchise_continuity.json'),'utf8'));
const espnMapping=JSON.parse(fs.readFileSync(path.join(ROOT,'reference/team_id_map.json'),'utf8'));
const championshipHistory=JSON.parse(fs.readFileSync(path.join(ROOT,'reference/championship_history.json'),'utf8'));
const historicalScores=JSON.parse(fs.readFileSync(path.join(ROOT,'reference/historical_regular_season_scores.json'),'utf8'));
function embedded(id){
 const begin='<script id="'+id+'" type="application/json">';
 const a=html.indexOf(begin),b=html.indexOf('</script>',a+begin.length);
 assert.ok(a>=0 && b>a,'Missing embedded '+id);
 return JSON.parse(html.slice(a+begin.length,b));
}
assert.deepStrictEqual(embedded('fantasydata'),data,'External JSON and embedded fallback must match');
assert.deepStrictEqual(embedded('metricdefs'),definitions,'HTML definitions must come from one canonical file');
const historyEmbedded={
 league_id:championshipHistory.league_id,
 season_to_franchise:continuity.season_to_franchise,
 dashboard_to_espn:espnMapping.baseline_to_espn,
 champions:championshipHistory.champions
};
assert.deepStrictEqual(embedded('championships'),historyEmbedded,'Embedded champion metadata must match the verified reference files');
assert.deepStrictEqual(embedded('historicalscores'),historicalScores,'Embedded historical scores must come from the sanctioned reference file');
assert.equal(historicalScores.seasons.reduce((n,s)=>n+s.teams.reduce((n,t)=>n+t.scores.length,0),0),420);
assert.deepStrictEqual(championshipHistory.champions.map(x=>[x.season,x.espn_team_id,x.franchise_id]),[
 [2023,7,'franchise-07'],[2024,10,'franchise-10'],[2025,1,'franchise-01']
]);
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
 getElementById(id){const el=node(id);if(id==='fantasydata')el.textContent=JSON.stringify(data);if(id==='metricdefs')el.textContent=JSON.stringify(definitions);if(id==='championships')el.textContent=JSON.stringify(historyEmbedded);if(id==='historicalscores')el.textContent=JSON.stringify(historicalScores);return el;},querySelectorAll:()=>[],
 addEventListener(name,handler){events[name]=handler}
};
const fetch=async()=>({ok:true,json:async()=>data});
const script=html.match(/<script>\s*([\s\S]*?)<\/script>/);
assert.ok(script,'Dashboard JavaScript missing');
const instrumented=script[1].replace(/\}\)\(\);\s*$/,'globalThis.__championshipTest={franchiseFor,championshipYears,teamName};})();');
assert.notEqual(instrumented,script[1],'Champion renderer test hook could not be installed');
const sandbox={document:doc,window:{scrollTo(){}},fetch,console};
vm.runInNewContext(instrumented,sandbox,{timeout:5000});
const names=sandbox.__championshipTest;
assert.ok(names.teamName({espn_team_id:7,name:'The Load Warriors'},2023).includes('League champion: 2023'),'Historic 2023 winning alias gets trophy');
assert.ok(names.teamName({espn_team_id:10,name:'Mike Oxlong'},2024).includes('League champion: 2024'),'Historic 2024 winning alias gets trophy');
assert.ok(names.teamName({espn_team_id:1,name:"General's Dorm Room"},2025).includes('League champion: 2025'),'Historic 2025 winning alias gets trophy');
assert.ok(!names.teamName({espn_team_id:6,name:'Team Figueroa'},2023).includes('champion-trophy'),'Legacy slot 6 never inherits current franchise record');
assert.ok(!names.teamName({espn_team_id:3,name:'Quattro Padres'},2025).includes('champion-trophy'),'No unverified Quattro title');
assert.ok(!names.teamName({espn_team_id:7,name:'The Load Warriors'},2022).includes('champion-trophy'),'Unmapped years must never inherit a title');
async function main(){
 for(let i=0;i<8;i++)await Promise.resolve();
 let view=node('view').innerHTML;
 const click=(selector,dataset)=>events.click({target:{closest(q){return q===selector?{dataset}:null;}}});
 const tab=name=>{click('[data-tab]',{tab:name});return node('view').innerHTML;};
 const sub=(kind,value)=>{click('[data-'+kind+'-view]',{[kind+'View']:value});return node('view').innerHTML;};
 assert.deepStrictEqual((html.match(/class="navbtn[^"]*" data-tab="[^"]+"/g)||[]).map(x=>x.match(/data-tab="([^"]+)"/)[1]),['overview','teams','history']);
 assert.equal((node('mobileNav').innerHTML.match(/<option value=/g)||[]).length,3,'Mobile navigation also has three destinations');
 assert.ok(view.includes('League standings & scoring rank')&&view.includes('Schedule luck · extra wins'),'Overview presents standings and schedule luck');
 assert.ok(view.includes('League avg PF')&&view.includes('League form'),'League strength and trend context retained');
 assert.ok(view.includes('power-desktop')&&view.includes('power-table')&&view.includes('power-mobile-item'));
 assert.equal((view.match(/<tr class="[^"]*" data-select="/g)||[]).length,10);
 assert.ok(view.includes('All-play')&&view.includes('Extra wins')&&view.includes('Form'));
 assert.ok(view.includes('What if opponents changed?')&&view.includes('darkest = 1st'),'What-if simulation retained on demand');
 assert.ok(view.includes('How the numbers work'),'Definitions retained in disclosure');
 assert.ok(!view.includes('selhero refinedhero')&&!view.includes('roster-action'),'Remove duplicate selected-team hero/roster from Overview');
 assert.ok(!view.includes('overview-kpis'),'Remove redundant overview KPI group');
 assert.ok(!view.includes('Avg extra wins'),'Do not create a meaningless zero-sum headline');
 for(const [name,year] of [['The Domestic House Cats','2024'],['Project Haily Mary','2023'],["General&#39;s Dorm Room",'2025']]){
  assert.ok(view.includes(name+'<span class="champion-trophy"'),'Standings must mark '+name);
  assert.ok(view.includes('League champion: '+year),'Championship year available '+year);
 }
 assert.ok(!view.includes('Quattro Padres<span class="champion-trophy"'),'No unverified champion badges');
 assert.equal((node('teamSelect').innerHTML.match(/🏆/g)||[]).length,3,'Global team selector retains trophies');
 click('[data-expand-standing]',{expandStanding:'6'});
 view=node('view').innerHTML;
 assert.ok(view.includes('standing-detail-6')&&view.includes('View The Domestic House Cats'),'Mobile expansion retained');
 click('[data-expand-standing]',{expandStanding:'6'});
 assert.ok(!node('view').innerHTML.includes('id="standing-detail-6"'),'Expanded rows collapse');
 click('[data-select]',{select:'6'});
 view=node('view').innerHTML;
 assert.equal(node('pageTitle').textContent,'Teams','Overview team selection opens Teams');
 assert.ok(view.includes('tc-report')&&view.includes('The Domestic House Cats')&&view.includes('4–0'),'Team report immediately visible');
 assert.ok(view.includes('League champion: 2024'),'Trophy follows current franchise');
 assert.equal((view.match(/class="tc-stat"/g)||[]).length,4,'Card presents four secondary benchmarks');
 assert.ok(view.includes('TEAM DNA')&&view.includes('EXTRA WINS')&&view.includes('STARTER-WORTHY'));
 assert.ok(view.includes('ALL-PLAY')&&view.includes('AVG PF / WEEK')&&view.includes('RECENT FORM')&&view.includes('CEILING CAPTURED'));
 assert.ok(!view.includes("BENCH MISS")&&!view.includes("UNAVOIDABLE"),'Move bench and unavoidable detail to Lineup subview');
 assert.ok(view.includes('SCORING')&&view.includes('LINEUP SWR')&&view.includes('CUMUL. LUCK'),'Preserve all three mini-trends');
 node('teamSelect').listeners.change({target:{value:'3'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('Israeli Nutonyaboob'));
 click('[data-card-step]',{cardStep:'1'});
 assert.ok(node('view').innerHTML.includes('Quattro Padres'),'Report-card stepping remains functional');
 node('teamSelect').listeners.change({target:{value:'3'}});
 view=sub('team','dna');
 assert.ok(view.includes('The Scoring Personality Map')&&view.includes('Franchise fingerprint · completed seasons only'),'DNA combines current map and historical identity');
 assert.equal((view.match(/<tspan dx="3" font-size="11">🏆<\/tspan>/g)||[]).length,3,'Map retains champion markers');
 assert.ok(view.includes('View season-by-season fingerprint, weights and lifetime baseline'),'Historical methods progressively disclosed');
 assert.ok(view.includes('Current 2026 DNA:')&&view.includes('Recent scoring trend'),'Current-season detail accessible');
 assert.ok(!view.includes('lineup-quality'),'Lineup no longer dominates DNA view');
 node('teamSelect').listeners.change({target:{value:'8'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('+8.5%')&&view.includes('15.1%'),'GDR historical scoring and volatility retained');
 node('teamSelect').listeners.change({target:{value:'10'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('2025 62.5% · 2024 37.5%')&&!view.includes('Team Figueroa'),'Current franchise excludes legacy 2023 ownership');
 view=sub('team','lineup');
 assert.ok(view.includes('lineup-quality')&&view.includes('Roster ceiling')&&view.includes('Weekly lineup quality'),'Deep lineup analysis kept');
 assert.ok(view.includes('Bench upgrades:')&&view.includes('Weekly opponent scores'),'Original lineup/box-score evidence stays available');
 assert.ok(view.includes('K/DST half-weighted'),'Preserve roster methodology');
 view=tab('history');
 assert.ok(view.includes('2025 Yearbook')&&view.includes('Regular-season scoring order'),'Yearbook built from actual completed scoring');
 assert.ok(view.includes('Rebuilt Golden Ponies'),'2025 scoring leader visible');
 assert.ok(view.includes('General&#39;s Dorm Room')&&view.includes('League champion: 2025'));
 assert.ok(view.includes('not official standings or playoff seeding'),'Do not mislabel PF ranking');
 assert.equal((view.match(/<tbody><tr>[\\s\\S]*?<\\/tbody>/)||[])[0]?.match(/<tr>/g)?.length,10,'Yearbook ranks exactly ten verified teams');
 events.change({target:{id:'historyYear',value:'2023'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('2023 Yearbook')&&view.includes('Team Figueroa'),'Legacy franchise remains in league yearbook');
 assert.ok(view.includes('The Load Warriors')&&view.includes('League champion: 2023'),'Historical champion alias receives trophy');
 view=sub('history','titles');
 assert.ok(view.includes('Championship Archive'));
 for(const [name,year] of [['The Load Warriors',2023],['Mike Oxlong',2024],["General&#39;s Dorm Room",2025]]){
  assert.ok(view.includes(name)&&view.includes(year+' champion'),'Every verified title preserved');
 }
 assert.ok(!view.includes('Quattro Padres'),'No invented historical championship');
 view=sub('history','legacy');
 assert.ok(view.includes('Franchise Legacy'));
 assert.ok(view.includes('Got Rice?')&&view.includes('2025')&&view.includes('2024'),'Current slot-6 franchise retains two known seasons');
 assert.ok(!view.includes('Team Figueroa'),'2023 owner cannot inherit legacy history');
 click('[data-tab]',{tab:'overview'});
 assert.equal(node('pageTitle').textContent,'League overview');
 console.log('Three-destination dashboard regression checks passed: standings, luck, expanded detail, team reports/DNA/lineup, source-backed history, trophies and ownership continuity.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
