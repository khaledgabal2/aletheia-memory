import assert from "node:assert/strict";
import createClient from "openapi-fetch";
import type {paths, components} from "./generated/onboarding.js";
import {Reviewer} from "./review-client.js";

const url=process.env.ALETHEIA_TEST_URL, token=process.env.ALETHEIA_TEST_TOKEN, operator=process.env.ALETHEIA_TEST_REVIEWER;
assert(url && token && operator);
const client=createClient<paths>({baseUrl:url,headers:{Authorization:`Bearer ${token}`}});
const principal=await client.GET('/v1/auth/me');
assert(principal.data);
assert(principal.data.data.supported_profiles.includes('agent-onboarding-v1'));
assert(!principal.data.data.capabilities.includes('memory:review'));
const input: components['schemas']['RememberCandidateRequest']={namespace:'user/phase0-demo',memory_type:'preference',subject:'user',predicate:'prefers',
  object:'careful architecture notes',evidence_text:'User prefers careful architecture notes.'};
const request={params:{header:{'X-Aletheia-Contract':'agent-onboarding-v1' as const,'Idempotency-Key':'typed-agent'}},body:input};
const captured=await client.POST('/v1/remember',request);
assert(captured.data?.data.write_mode==='candidate');
const replay=await client.POST('/v1/remember',request);
assert(replay.data?.data.candidate.id===captured.data.data.candidate.id);
const before=await client.POST('/v1/retrieve',{body:{namespace:input.namespace,query:'architecture',mode:'lexical'}});
assert.equal(before.data?.data.length,0);
// Separate operator fixture. A real application must collect a human decision.
const reviewer=new Reviewer(url,operator);
const inspected=await reviewer.inspect(captured.data.data.candidate.id);
const receipt=await reviewer.decide(inspected.id,'promote','Explicit synthetic contract-test approval',inspected.revision,'typed-agent-review');
assert(receipt.claim_id);
const context=await client.POST('/v1/context-pack',{body:{namespace:input.namespace,query:'architecture',retrieval_mode:'lexical',record_usage:false}});
assert(context.data?.data.items.some(item=>item.claim_id===receipt.claim_id));
const explained=await client.GET('/v1/claims/{claim_id}/explain',{params:{path:{claim_id:receipt.claim_id}}});
assert.equal(explained.data?.data.evidence[0]?.content,input.evidence_text);
console.log('Generated onboarding client: restricted principal, candidate creation, replay, empty trusted recall, separate governed approval, context and provenance passed.');
