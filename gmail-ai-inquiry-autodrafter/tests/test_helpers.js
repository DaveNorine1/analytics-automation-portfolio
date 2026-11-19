const assert=require('assert');const fs=require('fs');const vm=require('vm');
const src=fs.readFileSync(__dirname+'/../Code.gs','utf8');const sandbox={module:{exports:{}},console};vm.createContext(sandbox);vm.runInContext(src,sandbox);
const {pickRule_,guestCountFallback_,parseJson_,CONFIG}=sandbox.module.exports;
const cases=[
 [{type:'catering',guest_count:40},'Catering'],
 [{type:'private_event',guest_count:25},'Large private event'],
 [{type:'private_event',guest_count:10},'Small private event'],
 [{type:'private_event',guest_count:null},null],
 [{type:'other',guest_count:5},null]];
for(const [inq,exp] of cases){const r=pickRule_(inq,CONFIG.rules);assert.strictEqual(r?r.name:null,exp,JSON.stringify(inq))}
const counts=[['Number of guests: 25',25],['about 25 ppl',25],['Party size - approx 12',12],['We are 8 people',8],['Headcount: TBD',null]];
for(const [t,exp] of counts) assert.strictEqual(guestCountFallback_(t),exp,t);
assert.deepStrictEqual(JSON.parse(JSON.stringify(parseJson_('```json\n{"type":"catering","guest_count":30}\n```'))),{type:'catering',guest_count:30});
console.log(`all ${cases.length+counts.length+1} tests passed`);
