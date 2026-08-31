/** Separate agent process. Never receives the operator's review credential. */
import { agentClient } from "./transport.js";

const url=process.env.ALETHEIA_URL, token=process.env.ALETHEIA_AGENT_TOKEN;
const namespace=process.env.ALETHEIA_NAMESPACE ?? 'user/demo', action=process.argv[2];
if(!url || !token || !['capture','read'].includes(action ?? '')) {
  throw Error('Run operator_demo.py for a disposable local example, or supply URL, restricted token and capture/read action.');
}
const client=agentClient(url,token);
try {
  const result=await client.GET('/v1/auth/me');
  if(!result.data)throw Error('Principal discovery unavailable.');
  const principal=result.data.data;
  if(!['agent-onboarding-v1','memory-read-v1'].every(p=>principal.supported_profiles.includes(p)))throw Error('Required profiles unavailable; no write attempted.');
  const capabilities=principal.capabilities;
  if(!['memory:read','memory:context','memory:write_candidate'].every(c=>capabilities.some(v=>v===c)) ||
      ['memory:review','memory:write_active','memory:admin'].some(c=>capabilities.some(v=>v===c)))throw Error('Use a restricted agent credential without review, active-write or admin access.');
  if(action==='capture'){
    const key=process.argv[3];
    if(!key)throw Error('Capture requires an explicit operation key as its second argument.');
    const response=await client.POST('/v1/remember',{
      params:{header:{'X-Aletheia-Contract':'agent-onboarding-v1','Idempotency-Key':key}},
      body:{namespace,memory_type:'preference',write_mode:'candidate',subject:'user',predicate:'prefers',
        object:'careful architecture notes',evidence_text:'User prefers careful architecture notes.'}});
    if(!response.data)throw Error('Outcome unknown: retain the same operation key and payload.');
    console.log(JSON.stringify({candidate_id:response.data.data.candidate.id}));
  }else{
    const response=await client.POST('/v1/context-pack',{params:{header:{'X-Aletheia-Contract':'memory-read-v1'}},body:{namespace,query:'architecture',retrieval_mode:'lexical',record_usage:false}});
    if(!response.data)throw Error('Context unavailable.');
    const pack=response.data.data;
    console.log(pack.markdown);
    console.log('Visible context items:',pack.items.length);
    if(pack.items[0]){
      const detail=await client.GET('/v1/claims/{claim_id}/explain',{params:{path:{claim_id:pack.items[0].claim_id},header:{'X-Aletheia-Contract':'memory-read-v1'}}});
      console.log('Provenance:',detail.data?.data.evidence[0]?.content ?? 'No visible evidence');
    }
  }
}catch(error){
  console.error(error instanceof Error ? error.message : 'Memory operation failed; do not blindly repeat a write.');
  process.exitCode=1;
}
