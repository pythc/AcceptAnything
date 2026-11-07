"""Provider-specific evidence; never infer an unreported reasoning effort."""
import re


def flash_model(value):
    return isinstance(value,str) and bool(re.fullmatch(r'deepseek-(?:flash|v4\.1-flash(?:-\d{4})?)',value))


def verified_connection(connection):
    c=connection or {}
    if not c.get('verified') or c.get('finish_reason')!='stop':return False
    if c.get('provider')=='chat2api':
        return (c.get('requested_model')=='gpt-6-thinking' and c.get('reasoning_effort')=='high' and
                c.get('actual_model')=='gpt-6-thinking' and c.get('actual_thinking_effort')=='extended')
    if c.get('provider')=='deepseek':
        return bool(c.get('official_endpoint') and c.get('requested_model')=='deepseek-flash' and
                    c.get('reasoning_effort')=='high' and c.get('thinking')=='enabled' and flash_model(c.get('actual_model')))
    return False


def label(connection):
    c=connection or {}
    if c.get('provider')=='chat2api':return 'GPT-6 Thinking · High'
    if c.get('provider')=='deepseek':return 'DeepSeek Flash · High（请求设置）'
    return c.get('actual_model') or c.get('requested_model') or '模型辅助设计'


def response_matches(raw,connection):
    if not verified_connection(connection) or raw.get('model')!=connection.get('actual_model'):return False
    if connection['provider']=='chat2api':return raw.get('thinking_effort')=='extended'
    return flash_model(raw.get('model'))
