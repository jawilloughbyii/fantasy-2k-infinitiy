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
const playoffHistory=JSON.parse(fs.readFileSync(path.join(ROOT,'reference/historical_playoff_brackets.json'),'utf8'));
const draftHistory=JSON.parse(fs.readFileSync(path.join(ROOT,'reference/historical_draft_picks.json'),'utf8'));
const legacyDrafts=JSON.parse(fs.readFileSync(path.join(ROOT,'reference/historical_legacy_draft_picks_2014_2017.json'),'utf8'));
const gradedDrafts=JSON.parse(fs.readFileSync(path.join(ROOT,'reference/historical_draft_grades.json'),'utf8'));

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
 champions:championshipHistory.champions,
 legacy_champions:championshipHistory.legacy_champions
};
assert.deepStrictEqual(embedded('championships'),historyEmbedded,'Embedded champion metadata must match the verified reference files');
assert.deepStrictEqual(embedded('historicalscores'),historicalScores,'Embedded historical scores must come from the sanctioned reference file');
assert.deepStrictEqual(embedded('historicalplayoffs'),playoffHistory,'Embedded playoffs must match the validated bracket reference');
assert.deepStrictEqual(embedded('historicaldrafts'),draftHistory,'Embedded drafts must match source-verified JSON');
assert.deepStrictEqual(embedded('legacydrafts'),legacyDrafts,'Embedded 2014-17 ESPN drafts must match source-verified JSON');
assert.deepStrictEqual(embedded('historicaldraftgrades'),gradedDrafts,'Published grading matches verified reference');
assert.equal(gradedDrafts.coverage.pick_count,820);

assert.equal(draftHistory.seasons.reduce((n,s)=>n+s.picks.length,0),980,'980 actual ESPN draft picks');
assert.equal(historicalScores.seasons.reduce((n,s)=>n+s.teams.reduce((n,t)=>n+t.scores.length,0),0),1260);
assert.deepStrictEqual(historicalScores.seasons.map(s=>s.year),[2014,2015,2016,2017,2021,2022,2023,2024,2025]);
assert.equal(legacyDrafts.seasons.reduce((n,s)=>n+s.picks.length,0),680);
assert.equal(legacyDrafts.seasons.reduce((n,s)=>n+s.picks.filter(p=>p.player_name&&p.position).length,0),680);
assert.deepStrictEqual(championshipHistory.champions.map(x=>[x.season,x.espn_team_id,x.franchise_id]),[
 [2021,3,'franchise-07'],[2022,5,'franchise-03'],[2023,7,'franchise-07'],[2024,10,'franchise-10'],[2025,1,'franchise-01']
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
 getElementById(id){const el=node(id);if(id==='fantasydata')el.textContent=JSON.stringify(data);if(id==='metricdefs')el.textContent=JSON.stringify(definitions);if(id==='championships')el.textContent=JSON.stringify(historyEmbedded);if(id==='historicalscores')el.textContent=JSON.stringify(historicalScores);if(id==='historicalplayoffs')el.textContent=JSON.stringify(playoffHistory);if(id==='historicaldrafts')el.textContent=JSON.stringify(draftHistory);if(id==='legacydrafts')el.textContent=JSON.stringify(legacyDrafts);if(id==='historicaldraftgrades')el.textContent=JSON.stringify(gradedDrafts);return el;},querySelectorAll:()=>[],
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
assert.deepStrictEqual(championshipHistory.legacy_champions.map(x=>[x.season,x.espn_team_id,x.source_league_id]),[[2014,8,791996],[2016,9,791996],[2017,3,791996]]);
for(const [year,tid,alias] of [[2014,8,"Sleazy Veasey's Teenie Peenie"],[2016,9,"Jaqiuzz so much I Philip Rivers"],[2017,3,"The Bear Jew"]]){
 assert.ok(names.teamName({espn_team_id:tid,name:alias},year).includes('League champion: '+year),'Old-era winning alias gets trophy only in the winning season');
 assert.ok(!names.teamName({espn_team_id:tid,name:alias},2015).includes('champion-trophy'),'Old-era team IDs do not inherit trophies in disputed 2015');
}
assert.ok(!names.teamName({espn_team_id:2,name:'The General\'s "Dorm Room"'},2015).includes('champion-trophy'),'Disputed 2015 ESPN final must not receive trophy');
assert.ok(!names.teamName({espn_team_id:8,name:'Cuckleberry Finn'},2017).includes('champion-trophy'),'Runner-up must not receive trophy');
assert.ok(names.teamName({id:3,name:'Israeli Nutonyaboob'},2026).includes('2014'),'Confirmed current franchise inherits 2014 trophy');
assert.ok(names.teamName({id:4,name:'Golden Ponies'},2026).includes('2016'),'Confirmed Golden Ponies inherit 2016 trophy');
assert.ok(names.teamName({id:1,name:'Aubreys 3rd Leg'},2026).includes('2017'),'Confirmed winning franchise inherits 2017 trophy');
assert.ok(names.teamName({espn_team_id:3,name:'Lord Farquaad'},2021).includes('League champion: 2021'),'2021 winner has the season trophy');
assert.ok(names.teamName({espn_team_id:5,name:'Quatro Padres'},2022).includes('League champion: 2022'),'2022 winner has the season trophy');
assert.ok(names.teamName({id:7,name:'Project Haily Mary'},2026).includes('2021, 2023'),'Current 2026 franchise owns both 2021 and 2023 titles');
assert.ok(names.teamName({id:5,name:'Quattro Padres'},2026).includes('League champion: 2022'),'Current Padres retain verified 2022 title');
assert.ok(names.teamName({espn_team_id:7,name:'The Load Warriors'},2023).includes('League champion: 2023'),'Historic 2023 winning alias gets trophy');
assert.ok(names.teamName({espn_team_id:10,name:'Mike Oxlong'},2024).includes('League champion: 2024'),'Historic 2024 winning alias gets trophy');
assert.ok(names.teamName({espn_team_id:1,name:"General's Dorm Room"},2025).includes('League champion: 2025'),'Historic 2025 winning alias gets trophy');
assert.ok(!names.teamName({espn_team_id:6,name:'Team Figueroa'},2023).includes('champion-trophy'),'Legacy slot 6 never inherits current franchise record');
assert.ok(!names.teamName({espn_team_id:3,name:'Quattro Padres'},2025).includes('champion-trophy'),'No unverified Quattro title');
assert.ok(!names.teamName({espn_team_id:7,name:'The Load Warriors'},2022).includes('champion-trophy'),'Older historical years must never inherit titles from future seasons');
async function main(){
 for(let i=0;i<8;i++)await Promise.resolve();
 let view=node('view').innerHTML;
 const click=(selector,dataset)=>events.click({target:{closest(q){return q===selector?{dataset}:null;}}});
 const tab=name=>{click('[data-tab]',{tab:name});return node('view').innerHTML;};
 const sub=(kind,value)=>{click('[data-'+kind+'-view]',{[kind+'View']:value});return node('view').innerHTML;};
 assert.deepStrictEqual((html.match(/class="navbtn[^"]*" data-tab="[^"]+"/g)||[]).map(x=>x.match(/data-tab="([^"]+)"/)[1]),['overview','teams','history']);
 assert.equal((node('mobileNav').innerHTML.match(/<option value=/g)||[]).length,3,'Mobile navigation also has three destinations');
 assert.ok(html.includes('id="weekStatus"')&&!html.includes('id="sourceStatus"')&&!html.includes('id="sideStatus"')&&!html.includes('id="footerStatus"'),'Only one persistent data-status indicator remains');
 assert.equal(node('weekStatus').textContent,'2026 · Finalized through Week 4','Data-status indicator is based on approved completed weeks');
 assert.ok(view.includes('League standings & scoring rank')&&view.includes('Schedule luck · extra wins'),'Overview presents standings and schedule luck');
 assert.ok(view.includes('League avg PF')&&view.includes('League form'),'League strength and trend context retained');
 assert.ok(view.includes('power-desktop')&&view.includes('power-table')&&view.includes('power-mobile-item'));
 assert.equal((view.match(/<tr class="[^"]*" data-select="/g)||[]).length,10);
 assert.ok(view.includes('All-play')&&view.includes('Extra wins')&&view.includes('Form'));
 assert.ok(view.includes('What if opponents changed?')&&view.includes('Alternative completed schedules, not future forecasts.'),'What-if simulations and their retrospective caveat remain');
 assert.ok(view.includes('How the numbers work'),'Definitions retained in disclosure');
 assert.ok(view.includes('Positive = favorable schedule · Negative = tougher draw'),'Short luck legend replaces repeated formula');
 assert.ok(!view.includes('PF ranks teams by points scored, not predicted strength.')&&!view.includes('All-play compares each score against all nine teams'),'Remove repeated standings methodology footer');
 assert.ok(view.includes('Ranked by total points scored'),'Preserve PF ranking context in heading');

 const topicNames=['Results & Schedule Luck','Scoring & Team DNA','Lineup Quality','Historical Franchise DNA','Data & Reliability'];
 assert.equal((view.match(/<details class="method-topic">/g)||[]).length,5,'Exactly five concise methodology topics appear inside Overview');
 assert.equal((view.match(/<div class="method-item">/g)||[]).length,17,'All 17 metric explanations remain accessible');
 for(const topic of topicNames)assert.ok(view.includes('<summary><strong>'+topic+'</strong>'),'Missing calculation topic: '+topic);
 assert.ok(!view.includes('<details class="method-topic" open'),'All methodology topics start collapsed');
 for(const phrase of ['What it measures','How we calculate it','How to read it'])assert.ok(view.includes(phrase),'Each metric uses approachable explanatory language');
 assert.ok(view.includes('Actual wins − all-play expected wins'),'Extra wins is plainly explained');
 assert.ok(view.includes('above 20% CV'),'DNA CV cutoff is derived from the shared definitions');
 assert.ok(!view.includes('${m.')&&!view.includes('${fmt('),'No unresolved template expressions may appear in rendered definitions');
 assert.ok(view.includes('From Week 6'),'Momentum calculation uses the canonical full-window switch');
 assert.ok(view.includes('Weighted qualifying points ÷ 8'),'Starter-Worthy Rate uses canonical eight weighted slots');
 assert.ok(view.includes('at least 3 independent weekly pregame captures'),'Pregame verification gate is preserved');
 assert.ok(view.includes('Latest completed season: 50%; previous: 30%; third: 20%'),'Historical DNA weights match the canonical definition');
 assert.ok(view.includes('2023 ESPN slot 6 belongs to a different owner'),'Historical continuity boundary stays clear');
 assert.ok(view.includes('unavailable—not a zero score'),'Missing measurements are not zero-filled');
 assert.ok(!view.includes('class="method-details"'),'Old nested technical prose is replaced, not duplicated');
 assert.ok(!view.includes('\\n <h3>Pregame projections'),'Literal escaped newline is not rendered in the method section');

 assert.ok(!view.includes('selhero refinedhero')&&!view.includes('roster-action'),'Remove duplicate selected-team hero/roster from Overview');
 assert.ok(!view.includes('overview-kpis'),'Remove redundant overview KPI group');
 assert.ok(!view.includes('Avg extra wins'),'Do not create a meaningless zero-sum headline');
 for(const [name,year] of [['The Domestic House Cats','2024'],['Project Haily Mary','2021, 2023'],["General&#39;s Dorm Room",'2025']]){
  assert.ok(view.includes(name+'<span class="champion-trophy"'),'Standings must mark '+name);
  assert.ok(view.includes('League champion: '+year),'Championship year available '+year);
 }
 assert.ok(view.includes('Quattro Padres<span class="champion-trophy"'),'Verified 2022 champion must receive current trophy');
 assert.equal((node('teamSelect').innerHTML.match(/🏆/g)||[]).length,7,'Global team selector displays seven title-owning franchises');
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
 assert.ok(!view.includes('Screenshot the dark report card')&&!view.includes('tc-outside-note'),'Report Card no longer adds screenshot instructions');
 assert.ok(view.includes('LINEUP DETAILS: TEAMS → LINEUP'),'Useful action/context remains on the report card');
 node('teamSelect').listeners.change({target:{value:'3'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('Israeli Nutonyaboob'));
 click('[data-card-step]',{cardStep:'1'});
 assert.ok(node('view').innerHTML.includes('Quattro Padres'),'Report-card stepping remains functional');
 node('teamSelect').listeners.change({target:{value:'3'}});
 view=sub('team','dna');
 assert.ok(view.includes('The Scoring Personality Map'),'Keep Scoring Personality Map after concise summary');
 const identityStart=view.indexOf('<section class="identity-strip"'),identityEnd=view.indexOf('</section>',identityStart);
 assert.ok(identityStart>=0&&identityEnd>identityStart,'One unified identity card');
 const identity=view.slice(identityStart,identityEnd);
 const collapsed=identity.split('<details class="deep-dive identity-details">')[0];
 assert.equal((collapsed.match(/class="identity-era"/g)||[]).length,2,'Exactly two compact identity columns');
 assert.ok(collapsed.includes('CURRENTLY · 2026')&&collapsed.includes('HISTORICALLY · 2023, 2024, 2025'),'Current versus history is immediately visible');
 assert.ok(collapsed.includes('Volatile underdogs')&&collapsed.includes('Steady, lower-output'),'Initial franchise has distinct current versus historical classifications');
 assert.ok(collapsed.includes('PF/wk')&&collapsed.includes('23.7% CV'),'Concise current scoring details are visible');
 assert.ok(collapsed.includes('Differs from its recency-weighted franchise tendency.'),'Comparison is readable without expanding');
 assert.ok(collapsed.includes('Heating up · +50.7 PF/wk'),'Preserve momentum as a compact badge');
 assert.ok(!collapsed.includes('Typical scoring strength')&&!collapsed.includes('Historical consistency'),'Advanced metrics are not in initial visible summary');
 assert.ok(identity.includes('<details class="deep-dive identity-details"><summary>Historical metrics & season-by-season details</summary>'),'One collapsed advanced details section');
 assert.ok(!identity.includes('<details class="deep-dive identity-details" open'),'Historical details start collapsed');
 assert.ok(identity.includes('Typical scoring strength')&&identity.includes('Typical weekly volatility')&&identity.includes('Historical consistency'),'Keep all advanced metrics available');
 assert.ok(identity.includes('Season-by-season fingerprint')&&identity.includes('Rolling weights: 2025 50.0% · 2024 30.0% · 2023 20.0%'),'Keep yearly source breakdown');
 assert.equal((view.match(/<section class="identity-strip"/g)||[]).length,1,'No repeated hero/historical card');
 assert.ok(view.indexOf('The Scoring Personality Map')>identityEnd,'Scoring map follows concise identity card');
 assert.ok(!view.includes("class='card histdna'"),'No redundant standalone historical card');

 assert.equal((view.match(/<tspan dx="3" font-size="11">🏆<\/tspan>/g)||[]).length,7,'Map marks seven title-owning franchises');
 assert.ok(view.includes('Historical metrics & season-by-season details'),'Historical methods progressively disclosed');
 assert.ok(view.includes('Dashed splits:')&&view.includes('% CV.'),'Keep actual scoring-map split legend');
 assert.ok(!view.includes('Labels may use leader lines'),'Remove redundant visual mechanics from map footer');
 assert.ok(view.includes('CURRENTLY · 2026')&&view.includes('Recent scoring trend'),'Current-season detail accessible');
 assert.ok(!view.includes('lineup-quality'),'Lineup no longer dominates DNA view');
 node('teamSelect').listeners.change({target:{value:'8'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('+8.5%')&&view.includes('15.1%'),'GDR historical scoring and volatility retained');
 node('teamSelect').listeners.change({target:{value:'10'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('2025 50.0% · 2024 30.0% · 2022 20.0%')&&!view.includes('Team Figueroa'),'Returning franchise uses its own 2022 results but excludes the 2023 owner');
 view=sub('team','lineup');
 assert.ok(view.includes('lineup-quality')&&view.includes('Roster ceiling')&&view.includes('Weekly lineup quality'),'Deep lineup analysis kept');
 assert.ok(view.includes('Bench upgrades:')&&view.includes('Weekly opponent scores'),'Original lineup/box-score evidence stays available');
 assert.ok(view.includes('Finalized hindsight, not pregame predictions.')&&view.includes('Week 4 cutoff:'),'Retain crucial hindsight caveat and actual final-week cutoff');
 view=tab('history');
 assert.ok(view.includes('2025 Yearbook')&&view.includes('Regular-season scoring order'),'Yearbook built from actual completed scoring');
 assert.ok(!view.includes('This yearbook uses finalized regular-season scoring data.'),'Do not repeat yearbook methodology');
 assert.ok(view.includes('Rebuilt Golden Ponies'),'2025 scoring leader visible');
 assert.ok(view.includes('General&#39;s Dorm Room')&&view.includes('League champion: 2025'));
 assert.ok(view.includes('PF-ranked, not official W–L standings.'),'Do not mislabel PF ranking');
 assert.equal((view.split('<tbody>')[1].split('</tbody>')[0].match(/<tr>/g)||[]).length,10,'Yearbook ranks exactly ten verified teams');

 events.change({target:{id:'historyYear',value:'2014'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('2014 Yearbook')&&view.includes('Lucille&#39;s Baby Daddy')&&view.includes('Sleazy Veasey'),'2014 archived yearbook and final are visible');
 events.change({target:{id:'historyYear',value:'2015'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('2015 Yearbook')&&view.includes('ESPN final winner*')&&view.includes('title remains unverified'),'Disputed 2015 championship is disclosed without title certification');
 events.change({target:{id:'historyYear',value:'2017'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('2017 Yearbook')&&view.includes('The Bear Jew'),'2017 yearbook available');
 events.change({target:{id:'historyYear',value:'2025'}});
 view=node('view').innerHTML;
 events.change({target:{id:'historyYear',value:'2023'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('2023 Yearbook')&&view.includes('Team Figueroa'),'Legacy franchise remains in league yearbook');
 events.change({target:{id:'historyYear',value:'2022'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('2022 Yearbook')&&view.includes('Puss in Boots'),'Archived 2022 historical names and yearbook are available');
 assert.ok(view.includes('one starting punter (P)')&&view.includes('Lineup Quality is not available'),'Punter-era scoring is disclosed without unsupported lineup quality');
 assert.ok(view.includes('Quatro Padres')&&view.includes('League champion: 2022'),'2022 Yearbook confirms Quatro Padres championship');
 events.change({target:{id:'historyYear',value:'2021'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('2021 Yearbook')&&view.includes('Fully Staffed Young Hoes'),'Archived 2021 historical teams are available');
 assert.ok(view.includes('Lord Farquaad')&&view.includes('League champion: 2021'),'2021 Yearbook confirms Lord Farquaad championship');
 events.change({target:{id:'historyYear',value:'2023'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('The Load Warriors')&&view.includes('League champion: 2023'),'Historical champion alias receives trophy');
 view=sub('history','titles');
 assert.ok(view.includes('Championship Archive'));
 assert.ok(view.includes('2014 champion')&&view.includes('2016 champion')&&view.includes('2017 champion'),'Unified archive lists all three old-era title winners');
 assert.ok(view.includes('League champion: 2014')&&view.includes('League champion: 2016')&&view.includes('League champion: 2017'),'All old-era winner cards use trophy markers');
 assert.ok(view.includes('Eight verified championships across recovered years')&&!view.includes('Titles were reconstructed from ESPN postseason matchup progression'),'Verified title coverage without verbose footer');
 for(const [name,year] of [['Lord Farquaad',2021],['Quatro Padres',2022],['The Load Warriors',2023],['Mike Oxlong',2024],["General&#39;s Dorm Room",2025]]){
  assert.ok(view.includes(name)&&view.includes(year+' champion'),'Every verified title preserved');
 }
 assert.ok(view.includes('Quattro Padres'),'The current Padres franchise is identified for its historical title');
 assert.ok(view.includes('2025 Playoff bracket')&&view.includes('Comepig')&&view.includes('seed 7'),'2025 bracket and seeding caveat appear');
 events.change({target:{id:'playoffYear',value:'2022'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('2022 Playoff bracket')&&view.includes('123.43')&&view.includes('109.77'),'2022 championship final is shown');
 assert.ok(view.includes('TimmyT&#39;s Golden Ponies')&&view.includes('Quatro Padres'),'Historic finalists use their season names');
 assert.equal((view.match(/class="playoff-match"/g)||[]).length,7,'All verified winner-bracket matches and first-round byes appear');
 events.change({target:{id:'playoffYear',value:'2021'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('2021 Playoff bracket')&&view.includes('Lord Farquaad')&&view.includes('Watertown Teapots'),'2021 final is available by changing the year');
 view=sub('history','draft');
 assert.ok(view.includes('id="draftTag"'),'Draft outcome selector is rendered');
 assert.ok(view.includes('Draft History · 2014–2026')&&view.includes('Jahmyr Gibbs'),'Current draft is selectable');
 assert.equal((view.split('<tbody id="draftRows">')[1].split('</tbody>')[0].match(/<tr>/g)||[]).length,160,'2026 draft displays all 160 picks');

 events.change({target:{id:'draftYear',value:'2014'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('Shady Akers')&&view.includes('ESPN player ID')&&view.includes('Adrian Peterson')&&view.includes('Verified original-year ESPN player metadata'),'2014 original ESPN draft shows authentic season-specific player names and positions');
 assert.equal((view.split('<tbody id="draftRows">')[1].split('</tbody>')[0].match(/<tr>/g)||[]).length,170,'2014 draft displays all 170 original picks');
 events.change({target:{id:'draftYear',value:'2016'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('The General&#39;s &quot;Dorm Room&quot;')&&view.includes('170 picks'),'2016 draft is available');
 events.change({target:{id:'draftYear',value:'2026'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('Jahmyr Gibbs'),'Changing from legacy draft to modern draft preserves modern view');
 events.change({target:{id:'draftYear',value:'2021'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('Christian McCaffrey')&&view.includes('Includes punters'),'2021 draft recovered with punctuated historical format');
 assert.equal((view.split('<tbody id="draftRows">')[1].split('</tbody>')[0].match(/<tr>/g)||[]).length,170,'2021 draft displays all 170 picks');
 events.change({target:{id:'draftPosition',value:'P'}});
 view=node('view').innerHTML;
 assert.equal((view.split('<tbody id="draftRows">')[1].split('</tbody>')[0].match(/<tr>/g)||[]).length,10,'Punter filter yields ten actual picks');
 events.change({target:{id:'draftYear',value:'2023'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('Team Figueroa')&&view.includes('Historical franchise'),'2023 departing owner is not relabeled as its successor');
 events.change({target:{id:'draftYear',value:'2024'}});
 view=node('view').innerHTML;
 assert.ok(view.includes('Got Rice?')&&view.includes('Alan&#39;s Cordon Bleu Cavern'),'Returning owner resolves to current display with original era alias');
 events.change({target:{id:'draftTag',value:'STEAL'}});
 view=node('view').innerHTML;
 assert.equal((view.split('<tbody id="draftRows">')[1].split('</tbody>')[0].match(/<tr>/g)||[]).length,15,'2024 source-verified steals are filterable');
 view=sub('history','legacy');
 assert.ok(view.includes('Franchise Legacy'));
 assert.ok(view.includes('Got Rice?')&&view.includes('2025')&&view.includes('2024')&&view.includes('2022')&&view.includes('2021'),'Returning franchise recovers old-league years');
 assert.ok(view.includes('Fully Staffed Young Hoes')&&view.includes('Let&#39;s Go Brandin'),'Historic aliases belong to current team owner');
 assert.ok(!view.includes('2023</td><td class="tiny">'),'Absent owner must have a gap in 2023');
 assert.ok(!view.includes('Team Figueroa'),'2023 owner cannot inherit legacy history');
 assert.ok(view.includes('2023 ESPN slot 6 belongs to a different franchise and is excluded here.'),'Affected franchise retains identity continuity caveat');
 click('[data-tab]',{tab:'overview'});
 assert.equal(node('pageTitle').textContent,'League overview');
 console.log('Three-destination dashboard regression checks passed: standings, luck, expanded detail, team reports/DNA/lineup, source-backed history, trophies and ownership continuity.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
