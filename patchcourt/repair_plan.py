"""Bounded declarative adapter repairs. Plans are data, never Python code."""
from copy import deepcopy
import json
from .reproductions import load_nvidia, MESSAGE_TYPES
from .semantic import compare_messages

PLAN_SCHEMA = {
    "type":"object", "additionalProperties":False,
    "required":["source", "id_field", "name_field", "arguments_field", "arguments_encoding", "preserve_legacy", "empty_content"],
    "properties":{
        "source":{"enum":["tool_calls","additional_kwargs"]},
        "id_field":{"enum":["id","name"]},
        "name_field":{"enum":["name","id"]},
        "arguments_field":{"enum":["args","name"]},
        "arguments_encoding":{"enum":["json","string"]},
        "preserve_legacy":{"type":"boolean"},
        "empty_content":{"enum":["null","keep"]},
    },
}

def validate_plan(plan):
    if not isinstance(plan,dict) or set(plan)!=set(PLAN_SCHEMA['required']):
        raise ValueError('Repair must contain exactly the declared mapping fields')
    for key,spec in PLAN_SCHEMA['properties'].items():
        if 'enum' in spec and (not isinstance(plan[key],str) or plan[key] not in spec['enum']):
            raise ValueError('Unsupported repair mapping: '+key)
        if spec.get('type')=='boolean' and type(plan[key]) is not bool:
            raise ValueError('preserve_legacy must be boolean')
    return deepcopy(plan)

def convert_with_plan(message, plan, converter=None):
    plan=validate_plan(plan)
    result=(converter or load_nvidia())(message)
    if not isinstance(message,MESSAGE_TYPES['AIMessage']):
        return result
    calls=message.tool_calls if plan['source']=='tool_calls' else message.additional_kwargs.get('tool_calls',[])
    if not isinstance(calls,list) or len(calls)>20:
        raise ValueError('Repair input call budget exceeded')
    if calls:
        converted=[]
        for call in calls:
            if not isinstance(call,dict): raise ValueError('Invalid normalized tool call')
            arguments=call[plan['arguments_field']]
            converted.append({'id':call[plan['id_field']],'type':'function','function':{
                'name':call[plan['name_field']], 'arguments':json.dumps(arguments,ensure_ascii=False,allow_nan=False) if plan['arguments_encoding']=='json' else str(arguments)}})
        result['tool_calls']=converted
        if result.get('content')=='' and plan['empty_content']=='null': result['content']=None
    elif not plan['preserve_legacy']:
        result.pop('tool_calls',None)
    return result

def convert_trace(messages,plan):
    converter=load_nvidia()
    output=[]
    roles={'assistant':'AIMessage','tool':'ToolMessage','user':'HumanMessage','system':'SystemMessage'}
    for message in messages:
        data=deepcopy(message); role=data.pop('role')
        if role=='assistant':
            data['tool_calls']=[{'id':c['id'],'name':c['function']['name'],'args':json.loads(c['function']['arguments']),'type':'tool_call'} for c in data.get('tool_calls',[])]
        output.append(convert_with_plan(MESSAGE_TYPES[roles[role]](**data),plan,converter))
    return output

def verify_plan(plan):
    """Independent expectations are not supplied to the proposal prompt."""
    from .counterexamples import tool_conversation
    plan=validate_plan(plan)
    base=tool_conversation()
    fixtures=[('two_calls',base),('plain_text',[{'role':'user','content':'Hello'}]),('system_text',[{'role':'system','content':'Stay accurate'}])]
    for name,args in [('nested_unicode',{'sku':'雪','nested':{'values':[True,False,None,0,1.5]}}),('empty_arguments',{}),('boolean_not_integer',{'enabled':True,'count':0})]:
        case=deepcopy(base)
        case[0]['tool_calls'][1]['function']['arguments']=json.dumps(args,ensure_ascii=False)
        fixtures.append((name,case))
    case=deepcopy(base);case[1]['content']='';fixtures.append(('empty_tool_result',case))
    results=[]
    for name,baseline in fixtures:
        try:
            candidate=convert_trace(baseline,plan)
            verdict=compare_messages(baseline,candidate)
            results.append({'name':name,**verdict})
        except (KeyError,ValueError,TypeError) as exc:
            results.append({'name':name,'status':'FAIL','reason':str(exc)})
    legacy=MESSAGE_TYPES['AIMessage'](additional_kwargs={'tool_calls':deepcopy(base[0]['tool_calls'])})
    try:
        actual=convert_with_plan(legacy,plan)
        preserved=actual.get('tool_calls')==base[0]['tool_calls']
    except (KeyError,ValueError,TypeError): preserved=False
    results.append({'name':'legacy_calls','status':'PASS' if preserved else 'FAIL'})
    return {'status':'VERIFIED' if all(r['status']=='PASS' for r in results) else 'REJECTED','checks':results,
            'scope':'Declarative mapping over hash-pinned upstream adapter with inert SDK message types; no model Python executed'}
