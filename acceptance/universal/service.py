"""Frozen generic capability plan. Partial issues affect coverage, not dispatch."""
import json,uuid,sys
from importlib.metadata import version
from pathlib import Path
from .discovery import discover,batches,relevant
from . import runtime
from ..integrations.discovery import inventory,manifest,prepare as scan_prepare
from ..integrations.runner import encode,sha
from ..integrations.registry import locks
from ..integrations.formats import require
from ..planning.models import DraftInput,Document
from ..planning import provider

STAGES=[dict(id=k,title=v) for k,v in [('discovery','仓库发现'),('scanners','仓库扫描'),('prepare','隔离环境准备'),('build','构建验证'),('native','原生测试'),('service','服务就绪'),('design','独立标准与用例'),('business','分项业务验证'),('cleanup','环境清理')]]

EXECUTION_CONTRACT=dict(version=21,
    fixture_builds='Python 用例若用 write_file 声明本地插件的 pyproject.toml，平台在独立的用例环境准备阶段按 PEP 517 静态声明下载 wheel。业务执行 PIP_NO_INDEX，缓存只读，并用已安装版本约束防止替换被验收项目或依赖。保留完整声明、解析/下载日志、wheel、摘要与每例挂载证据。缺少安全可核对的构建声明时只阻断相关用例，不放开业务网络。',
    isolated_case_state='每条用例从原生测试之前封存的准备/构建快照复制独立工作卷，包含同版本依赖与源码；不继承原生测试、前条用例或共享工作目录的数据库。每条用例的broker、worker、网络与Web应用都独立，保持文档中的localhost配置，不改目标代码；退出后回收整套容器、卷和网络。setup仍须通过公开API准备本条用例所需的业务数据，不得假设默认已有账号或历史。复制准备、服务就绪与回收原件逐条保留。',
    cli_error_outcomes='流程cli可对/exit_code使用json_schema整数约束；文档只说错误退出、不指定固定错误码时，可以明确断言非零区间，例如{"type":"integer","minimum":1,"maximum":255}，而不是猜测恒等于1。同时按文档断言错误信息或业务状态；不能只检查旁路状态、不核对错误结果。',
    routing='route_bindings从冻结源码的AST读取路由、方法、endpoint、Blueprint/APIRouter前缀与注册覆盖，仅用于接线，不是正确答案。文档明确规定的固定API路径必须原样测试，与实现不一致时保留失败，不得换路径通过。只有具体示例中明确以符号、url_for或示例简写指代路由时才解析真实前缀，并在reason说明转换依据。binding=registration-needs-binding或path=null时不可猜测。浏览器提交后必须核对页面结果，不能只在提交前检查表单可见再把接口轮询当成页面结果。',
    independent_requests='单条request可用pointer+expected+comparison即时核对真实HTTP回执，也可expected=null只采集；poll重复请求直到独立预期满足。均可capture供后续动作输入使用。页面goto和最终UI断言仍是完整journey必需步骤。相同语义模型输入的未知请求不会自动重发；不同仓库、独立文档批次或执行能力明确变更的新方案允许执行，原未知回执不改写。',
    service_graph='service_graph给出从冻结源码和文档命令识别的服务节点、来源与依赖。平台用Docker隔离运行本地服务与真实worker，绝不把任务改为同步/eager模式。用例需要后台任务时requires填写相关节点id；依赖失败仅阻断相关用例。supported=false的节点不得假设已准备。工作进程池solo、concurrency=1是执行资源配置，不代表性能验收。',
    browser_journey='完整浏览器流程使用kind=journey，顶层expected=null，journey={version:1,setup:[已有Step协议],cleanup:[],app:准备步骤的应用对象id,adapter:wsgi/asgi/node-listener,steps:[浏览器步骤]}。setup用公开API构造真实应用并准备独立数据库/文件；app必须是Flask/FastAPI/Fastify等真实应用对象。框架通过成熟Werkzeug/Uvicorn/Node监听器托管应用，监听随机端口，每用例独立进程、临时目录和浏览器context，最后关闭服务与清理。不得依赖原生测试留下的数据，也不需要/不得自行写.listen或.run步骤。',
    browser_steps='浏览器steps有id、action、selector(CSS)、path、value、expected、comparison、timeout_ms。action包括goto(path)、fill(selector,value)、click、press(value)、check/uncheck、select(value)、expect_text(默认equals/可contains)、expect_visible(expected布尔)、expect_hidden(expected=true)、expect_url(expected相对路径)、expect_value、expect_count、expect_attribute(attribute,expected)、expect_validity(expected为浏览器原生validity字段约束对象)。request/poll通过同源真实HTTP，method/form或body输入，回执{status,headers,value}；capture记录回执，后续path/value/form可用${变量:/value/id}输入插值；poll(pointer,expected,comparison)等待实际结果。预期不可引用捕获值。每条流程必须有业务断言；操作失败是执行异常，独立断言不符保留失败。timeout_ms仅等待预算，不是性能SLO。',
    browser_bindings='ui_bindings来自模板静态标签，仅用于定位器接线，不是业务正确性依据。静态模板可能有占位符，不可凭模板推导预期。服务路由前缀也仅用于接线。必须优先把文档中的注册→登录→创建/修改/删除、提交后台任务→轮询完成等完整用户路径设计为journey。删除等有原生confirm时，先用action=dialog,value=accept或dismiss声明下一次对话框响应，再点击，平台记录真实对话框；未触发也不放行。CLI/纯库没有声明Web应用时不强造页面，使用scenario/cli验证真实功能。异常捕获必须显式核对结果。',
    local_dependencies='Python组件可调用本组件与其直接本地依赖的已索引公开入口；依赖必须按冻结源码路径安装，同名歧义仍拒绝。第三方未索引库、未声明组件及不确定的传递依赖不自动放行。',
    model_budget='DeepSeek官方模型能力按每次/models响应冻结，输出预算从实际模型元数据获得并受上下文剩余保守预算约束，不固定为旧32k。完整响应流式落盘，超过内存阈值转磁盘，不按字节上限截断；length终态仍拒绝，未知状态不自动重试。',
    callback_fields='在args/kwargs/回调return中，{"$ref":"前序步骤或回调参数","pointer":"/body"}读取该对象的公开字段或数据键；pointer为非空RFC6901路径。可将实际请求参数（例如回调request的body）返回或传给公开reply方法，保留动态输入；不是引用预期值，缺失字段仍报错。可省略pointer引用整个对象。',
    binary_fixtures='write_file默认encoding=utf-8；可按独立依据声明latin-1、ascii或base64来准备非UTF8字节夹具。value仍是字符串，base64须为规范编码；不可编码字符拒绝而不截断。只在本用例临时目录写入输入文件，不改变仓库文件。',
    structured_results='comparison=json_schema时expected为JSON Schema 2020-12约束对象，宿主使用成熟jsonschema组件校验实际JSON值。适用于文档只规定类型、结构、数值区间而没有固定值的结果；如随机可用端口可检查整数且minimum=1。所有约束须来自独立依据，不得为了通过设计宽松Schema。支持本地片段引用，不支持外部资源、动态$id、pattern/patternProperties或空Schema；需要这些特性则保留缺口。',
    citation_binding='quote须逐字符取自指定文档，且在该片段中能唯一定位；重复句子必须连同周围上下文一起引用。仅RST代码块的共同外层缩进可定位，代码内部相对缩进、值与标点不能改写。',
    status_basis='状态码是独立断言，必须有引用原文中的具体数值依据；原文只说成功、未授权或重定向时，不得猜测200/401/302等具体数值。可使用原文明示的响应内容、目标地址或其他可观察行为设计用例。不要为让用例可执行放宽预期，缺少关键依据时保留缺口。',
    observations_extended='observe_call 与 call 使用相同的公开入口、参数和异步设置，但将目标调用实际抛出的异常记录为 {raised:true,exception:{type,message}}（Python另有module），正常返回记录为 {raised:false,return_observable:布尔,value:可观察结果}。只有目标调用异常会成为数据，入口/引用错误仍是用例异常；必须通过checks独立断言raised、异常类型或文档要求的信息，不得用于cleanup。identity 用 target 和 value:{"$ref":"另一前序步骤"}比较对象句柄是否同一个对象，不是内容相等；标量拒绝。inspect_path 的 target 是前序步骤返回的路径，读取{exists,is_file,is_dir,path}，仅限用例临时目录和隔离仓库，拒绝越界及逃逸链接；只观察，不写入。',
    contexts='enter 的 target 必须指向真正具有上下文协议的管理器，不是普通应用对象；若公开方法返回管理器，应先call该方法，再enter其返回对象。exit 的 target 可指向 enter 步骤 id，或唯一活动的原管理器 id。__enter__ 返回值可能不同，不得把它当成管理器再次退出；重复或歧义退出是错误。',
    alternatives='comparison=one_of时expected是文档明确允许的非空候选值数组；逐个进行严格类型相等比较，不把输出字符串截取后放行。监听可用port=0申请临时端口，通过公开server.address()读取address；预期可为["127.0.0.1","::1"]，仅当文档明确允许二者。必须cleanup关闭服务。',
    callback='回调可声明 calls:[{id:"sent",target:"reply",member:"send",args:[输入数据]}]，target只能为回调参数、前序步骤或前序回调调用id；支持kwargs和异步回调内await_result，return可以是JSON字面值（字符串、数字、布尔、null、数组或对象）或$ref；例如文档返回对象时写return:{"message":"ready"}。JavaScript原文没有return时必须省略return并写return_undefined:true，不能添加null；二者互斥，Python仅用return。回调公开方法调用及字面量参数必须忠实保留引用原文中的操作，不能把显式发送或配置方法改成return、不能省略。用例输入回调与实际调用结果分别留痕，回调接线异常即使用目标代码捕获也属于执行异常。',
    field_paths='checks.pointer使用RFC6901，例如/headers/content-type表示两个字段，/headers.content-type只表示一个带点字段名，不是嵌套访问。字典式公开对象按键读取（保留原对象的大小写规则），其他对象读取公开属性。需要读取thenable响应字段且包装对象上字段缺失或不可观察（例如同名构造方法）时驱动按需等待真实结果并记录awaited_result，不提前等待仍需配置的工厂。',
    cli_observation='CLI步骤返回{exit_code,stdout,stderr}完整回执，不是裸输出。检查命令输出必须pointer=/stdout（错误输出为/stderr），JSON输出用/stdout与json_stream；退出码用/exit_code和equals整数。禁止空pointer把整份回执当stdout比较。若确实检查整份回执，空pointer的expected必须是包含这三个字段的完整对象。',
    fixture_paths='cli.argv参数可以是普通相对文件名如data.csv，或结构化对象{"$path":"data.csv"}、{"$ref":"write_step"}；绝不能写成字符串"$path/data.csv"或模板字符串。每条用例自行准备输入文件；不得依赖别的用例文件。',
    format_retry='仅已核对模型且完整结束的正文JSON语法错误允许一次重新生成；保留两次原件；超时、未知状态和语义校验错误不自动重试',
    module='module仅用于一次普通函数调用；对象构造、回调和多步状态使用scenario。返回值使用JSON、dataclass或Pydantic标准表示，JSON Pointer选择观察字段',
    cli='已声明且会自行结束的CLI；不把长驻服务的启动提示当作CLI输出用例',
    service='独立http/browser协议需要唯一部署服务声明；scenario可以通过公开类/工厂在进程内创建应用、注册文档中的回调、用公开测试客户端或注入接口发送请求，无需常驻服务声明。进程内请求不证明部署或浏览器通过',
    state='没有预置账号或业务历史；scenario可在隔离临时目录准备数据库、文件和应用对象。不能依赖原生测试或其他用例副作用',
    setup='scenario协议支持独立临时工作目录、write_file文本夹具、公开类/工厂调用、实例方法、属性/索引读取、collect迭代器、Python enter/exit上下文；通过目标公开API播种真实测试数据库。$path相对临时目录，$ref引用前序步骤；$callback声明params、return或return_undefined、async及可选calls；仅通过已声明的公开方法动作，不执行任意代码。每用例独立进程，cleanup始终尝试，先前用例不会提供状态。没有任意脚本、外部账户或未声明的依赖服务。',
    scenario='kind=scenario时flow包含version=1、steps、cleanup、checks；步骤id唯一，op=call/observe_call/get/item/collect/identity/inspect_path/enter/exit/write_file/cli。call用module+export或target(前序步骤id)+member；省略member可调用前步返回的函数（如装饰器）。args/kwargs可含{"$ref":"步骤id"}、{"$path":"data.db"}或{"$callback":{"params":[],"return":"fixture","async":false}}。get读取公开member；item用value作索引；collect转换迭代结果；Node类需instantiate=true，工厂不要设true；真正Promise自动等待，其他thenable只在明确需要完成时设await_result=true，不要提前等待尚需配置的工厂对象。cli用entry选择本组件已声明命令，argv数组支持$path/$ref，stdin文本，输出为exit_code/stdout/stderr，与其他步骤共享临时目录。checks包含step、pointer、expected、comparison，由宿主断言；流程中的CLI JSON输出比较用json_stream，expected可为JSON文本或结构化JSON值；只做保留类型的序列化比较，不改写原值。Case顶层expected设null；不得仅断言构造成功。',
    plumbing='允许把文档示例翻译为等价声明步骤，无需示例文件已存在。discovery中的公开签名、类型和常规公开测试客户端仅用于接线、读回和清理，不提供正确答案；正确输出与适用条件只能来自documents。回调返回夹具是输入，必须通过实际路由请求/数据读取验证，不能直接断言回调本身。文档只写插入示例时可经公开查询读回相同数据；不能根据实现添加未声明行为保证。',
    configuration='只构造类并读回配置时，原文必须明确说明被检查属性的行为；不能凭实现签名或输入值猜测属性预期，不能把配置读回冒充无IO、上下文隔离或其他架构证明。缺少观察协议时保留未决。',
    observations='Python索引kind=property的成员用get读取，不能call；Node thenable对象保留配置能力，当后续读取成员或迭代结果无法在包装对象上进行时才等待实际结果，原件记录awaited_target。也可明确使用await_result=true。响应等带方法对象可用checks.pointer指定公开数据字段（选择该库真实存在的公开字段或调用其公开 getter；不得把其他库的 /body 字段移植到当前响应），驱动只接收字段路径，不接收预期值，并保存该字段的实际观察；不把对象句柄、函数或undefined当作JSON null或业务结果。',
    network='安装及测试收集预热后断开外网；正式执行启用模型库官方离线模式，只能使用已有缓存。未提供的模型权重或数据集不能假设存在，保留未覆盖项')


def planning_units(units):
    """Only callable protocol metadata belongs in the model context.

    The complete discovery, dependency settings and native test inventory stay
    in the frozen plan. They must not crowd out independent requirements.
    """
    rows=[]
    for u in units:
        row={k:u[k] for k in ('id','runtime','path','manifest','capabilities','interfaces','provides','entries','cli_commands','cli_origins','services','runtime_entry','native_commands','local_dependencies','service_graph','ui_bindings','route_bindings') if k in u}
        settings=u.get('settings',{});row['settings']={k:settings[k] for k in ('name','main','exports','source') if k in settings}
        if settings.get('project',{}).get('name'):row['settings']['project']={'name':settings['project']['name']}
        rows.append(row)
    return rows


def runtime_identity():
    lock=Path(__file__).parents[2]/'requirements.lock.txt'
    return dict(python=list(sys.version_info[:3]),requirements_sha256=sha(lock.read_bytes()),
                packages={name:version(name) for name in ('pydantic','jsonpointer','httpx','packaging','PyYAML')},resource_policy=runtime.resource_policy())


def implementation():
    from ..workflow import implementation as current
    return sha(encode(dict(code=current(),runtime=runtime_identity())))


def prepare(store,repository,remote_source=None):
    root,files,omitted=inventory(repository);rows=manifest(str(root),files);d=discover(root,files)
    from .documents import enrich
    doc_batches,retrieval=enrich(root,list(batches(root,d['documents'])),d['document_catalog'],d['units']);gaps=list(d['gaps'])
    # Short plan-local IDs reduce transcription errors; anchors still bind the
    # exact document origin, bytes and digest. Never repair model output IDs.
    for number,doc in enumerate((doc for batch in doc_batches for doc in batch),1):doc['id']='D'+str(number)
    if not d['units']:gaps.append(dict(kind='adapter',source='运行组件',reason='没有可执行的项目声明；通用扫描继续，运行与业务覆盖不成立'))
    if not doc_batches:gaps.append(dict(kind='basis',source='独立依据',reason='没有独立行为文档；扫描与构建继续，业务覆盖不成立'))
    scanned=scan_prepare(store,str(root),network=True,tests=False)
    original=json.loads((store.root/'plans'/(scanned['id']+'.json')).read_bytes())['record'];profile=original['profile']
    dag=[];tasks=[];rules=[];checks=[]
    def add(tid,kind,target='.',needs=None):
        tool='universal-'+kind
        registry=kind=='prepare' or kind=='native' and any(u['id']==target and u['runtime']=='python' for u in d['units'])
        tasks.append(dict(id=tid,tool=tool,target=target,timeout=3600,network='registry' if registry else 'none'))
        dag.append(dict(id=tid,stage=kind,needs=needs or []))
        checks.append(dict(id=tid,title={'design':'模型设计中文用例','prepare':'隔离环境与依赖','build':'构建与语法检查','native':'项目原生测试','service':'服务就绪','business':'独立业务用例','cleanup':'回收隔离环境'}[kind]+' · '+target,expected='执行真实命令和独立断言，异常与缺口不放行'))
        rules.append(dict(id=tid+'-failed',kind='metric',tasks=[tid],metric='tests.failed',operator='le',threshold=0))
    for i,_ in enumerate(doc_batches):add('design-'+str(i+1),'design',str(i))
    for t,c in zip(profile['tasks'],scanned['checks']):
        tasks.append(t);checks.append(c);dag.append(dict(id=t['id'],stage='scanners',needs=[]))
    rules+=profile['rules']
    designs=[t['id'] for t in tasks if t['tool']=='universal-design']
    def ordered(units):
        result=[];pending=list(units)
        while pending:
            ready=[u for u in pending if not set(u.get('local_dependencies',[]))-{x['id'] for x in result}]
            if not ready:
                gaps.append(dict(kind='dependency',source='组件依赖',reason='发现循环本地依赖；相关组件保留未决，不猜测安装顺序'))
                result+=pending;break
            for u in ready:result.append(u);pending.remove(u)
        return result
    for u in ordered(d['units']):
        uid=u['id'];needs=[x+'-prepare' for x in u.get('local_dependencies',[])]
        add(uid+'-prepare','prepare',uid,needs)
        built=u['runtime']!='node' or bool(u.get('syntax_files') or u['settings'].get('scripts',{}).get('build'))
        prereq=[uid+'-prepare']
        if built:
            add(uid+'-build','build',uid,prereq)
            # Syntax checks do not create a runtime artifact. A bad unrelated
            # source file must not suppress native collection or other cases.
            if u['runtime'] in {'go','rust'} or u['runtime']=='node' and u['settings'].get('scripts',{}).get('build'):prereq=prereq+[uid+'-build']
        if (u['runtime']=='python' and u['test_files']) or u['runtime']=='rust' or u['runtime']=='go' and u['test_files'] or u['runtime']=='node' and u['settings'].get('scripts',{}).get('test'):
            add(uid+'-native','native',uid,prereq)
        if 'http' in u['capabilities'] or u.get('service_graph',{}).get('nodes'):add(uid+'-service','service',uid,prereq)
        if u['capabilities']:add(uid+'-business','business',uid,[*prereq,*designs])
    add('universal-cleanup','cleanup')
    # Independent checks must finish even if a remote planning call stalls.
    # Model inputs receive readiness metadata only, never native-test answers.
    order={'universal-design':1,'universal-business':2,'universal-cleanup':3}
    tasks.sort(key=lambda t:order.get(t['tool'],0))
    exclusions=[e for e in profile['exclusions'] if e['subject'] not in {'仓库现有测试','业务流程、浏览器、性能与恢复'}]
    exclusions.append(dict(subject='未声明的性能SLO、故障恢复与外部生产系统',reason='没有独立阈值、故障模型或替身契约时保留覆盖缺口，不推测通过'))
    main=next((u for u in d['units'] if u['path']=='.'),{})
    declared_name=main.get('settings',{}).get('project',{}).get('name') or main.get('settings',{}).get('name')
    display_name=(remote_source or {}).get('name') or (declared_name if isinstance(declared_name,str) else None) or root.name
    profile.update(id='local-universal-'+uuid.uuid4().hex[:12],name=display_name+' · 通用验收',version='universal-v1',scope='自动发现、隔离环境、文档标准、独立用例与分项执行；覆盖缺口单独阻止放行',tasks=tasks,rules=rules,exclusions=exclusions)
    from ..integrations.models import Profile
    profile=Profile.model_validate(profile).model_dump()
    p=dict(id='auto-'+uuid.uuid4().hex[:16],kind='universal',repository=str(root),manifest=rows,snapshot_digest=sha(encode(rows)),discovery=d,batches=doc_batches,document_retrieval=retrieval,gaps=gaps,model_units=planning_units(d['units']),execution_contract=EXECUTION_CONTRACT,
        profile=profile,dag=dag,checks=checks,stages=STAGES,scope=profile['scope'],documents=[x['path'] for x in d['documents']],exclusions=exclusions,blockers=[],runtime_identity=runtime_identity(),implementation_digest=implementation(),toolchain_digest=sha(encode(locks())))
    from .fixture_preparation import augment
    augment(p)
    from .bindings import context
    p['projection_context']=context(d['units'])
    if remote_source:p['remote_source']=remote_source
    folder=store.root/'automatic-plans';folder.mkdir(exist_ok=True);digest=sha(encode(p));(folder/(p['id']+'.json')).write_bytes(encode(dict(record=p,sha256=digest)))
    return public(p,digest)


def public(p,digest):
    result=dict(id=p['id'],digest=digest,kind='universal',repository=p['repository'],ready=True,file_count=len(p['manifest']),check_count=len(p['profile']['tasks']),
        scope=p['scope'],stages=p.get('stages',STAGES),documents=p['documents'],exclusions=p['exclusions'],blockers=[],gaps=p['gaps'],
        universal=dict(units=[{k:u[k] for k in ('id','runtime','path','manifest','capabilities','interfaces','service_graph') if k in u} for u in p['discovery']['units']],interface_count=p['discovery']['interface_count'],documents=len(p['documents']),batches=len(p['batches']),gaps=p['gaps']))
    if p.get('document_retrieval'):result['document_retrieval']=p['document_retrieval']
    if p.get('frozen_design_run'):
        result['frozen_design_run']=p['frozen_design_run'];result['universal']['design_mode']='frozen-response-replay'
    if p.get('remote_source'):result['remote_source']=p['remote_source']
    return result


def create(store,pid,digest):
    from ..automatic import load,check_source
    p=load(store,pid,digest);require(p['kind']=='universal','方案类型无效');check_source(p)
    require(p['implementation_digest']==implementation() and p['toolchain_digest']==sha(encode(locks())),'执行器或环境版本变化，请重新识别')
    if p.get('remote_source'):
        from ..remote import verify
        verify(store,p['remote_source'])
    store.register(p['profile']);r=store.create(p['profile']['id'],prepared_plan=p)
    require(r['context']['snapshot_digest']==p['snapshot_digest'],'冻结时源码发生变化')
    r.update(universal_plan=p,universal_generation=dict(requirements=[],issues=list(p['gaps']),batches=[]),onboarding_plan={**public(p,digest),'checks':p['checks']})
    r['universal_plan_ref']=store.artifact(r,'universal-plan.json',encode(p))
    driver=store.path(r['id'])/'universal-driver';driver.mkdir()
    r['universal_drivers']={}
    for file in Path(__file__).parent.iterdir():
        if file.suffix not in {'.py','.cjs'}:continue
        raw=file.read_bytes();(driver/file.name).write_bytes(raw)
        r['universal_drivers'][file.name]=store.artifact(r,'universal-driver/'+file.name,raw)
    if p.get('remote_source'):
        from ..remote import bind_run
        bind_run(store,r,p['remote_source'])
    store.save(r);return r


def design_draft(store,data,cancelled,on_retry):
    """One bounded re-generation for a known completed syntax rejection only."""
    for attempt in range(2):
        if cancelled():raise ValueError('模型生成已取消')
        before={p.name for p in (store.root/'model-calls').glob('*.json')}
        try:return provider.draft(store,data)
        except ValueError:
            created=[p for p in (store.root/'model-calls').glob('*.json') if p.name not in before]
            receipt=json.loads(created[0].read_bytes()) if len(created)==1 else {}
            if attempt or receipt.get('state')!='rejected' or receipt.get('rejection_kind')!='json_syntax':raise
            on_retry(receipt)


def execute(store,r,t,output,cancelled):
    output.mkdir(parents=True,exist_ok=True);kind=t['tool'].removeprefix('universal-')
    if kind!='cleanup':require(r['universal_plan']['implementation_digest']==implementation() and r['universal_plan']['toolchain_digest']==sha(encode(locks())),'验收实现或工具链变化；此任务停止，环境仍会清理')
    node=next(n for n in r['universal_plan']['dag'] if n['id']==t['id'])
    deps=[x for x in r['tasks'] if x['id'] in node['needs']]
    def blocking(d):
        if d['state']!='completed':return True
        if d['tool'] in {'universal-design','universal-fixture'}:return False
        rows=d.get('report',{}).get('tests',[])
        if r['universal_plan']['execution_contract'].get('version',0)>=14 and d['tool']=='universal-prepare':
            # Optional setup errors remain gaps, while usable base environments
            # can execute unrelated checks and expose their own actual results.
            return not rows or rows[0]['status']!='passed' or any(x['status']!='passed' and not x['name'].startswith('可选准备 · ') for x in rows)
        return any(x['status']!='passed' for x in rows)
    bad=[d['id'] for d in deps if blocking(d)]
    require(not bad,'仅此分支前置条件未满足：'+', '.join(bad))
    if kind=='design':
        index=int(t['target']);docs=r['universal_plan']['batches'][index];interfaces,selection=relevant(r['universal_plan']['discovery']['interfaces'],docs)
        target=dict(context_version=2,units=r['universal_plan']['model_units'],interfaces=interfaces,selection=selection,execution_contract=r['universal_plan']['execution_contract'])
        if r['universal_plan']['execution_contract'].get('version',0)>=19:
            target['service_readiness']=[dict(unit=uid,id=n['id'],kind=n['kind'],status=n['status']) for uid,nodes in r.get('universal_graphs',{}).items() for n in nodes]
        if r['universal_plan'].get('document_retrieval'):target['document_scope']=r['universal_plan']['document_retrieval']['batches'][index]
        if r['universal_plan']['execution_contract'].get('version',0)>=4:target['types']=r['universal_plan']['discovery'].get('types',[])
        if r['universal_plan'].get('projection_context'):target['projection_context']=r['universal_plan']['projection_context']
        batch=dict(index=index,documents=[d['origin'] for d in docs],selection=selection)
        before={p.name for p in (store.root/'model-calls').glob('*.json')}
        try:
            data=DraftInput(repository=str(store.path(r['id'])/'source'),documents=docs,scope=r['universal_plan']['scope'],universal_target=target)
            def preserve_rejected(receipt):
                cid=receipt['client_request_id'];attempt=dict(client_request_id=cid,reason='json_syntax')
                for folder in ('model-calls','model-inputs','model-responses'):
                    p=store.root/folder/(cid+'.json')
                    if p.is_file():attempt[folder+'_ref']=store.artifact(r,f'model/format-retry-{index+1}-{folder}.json',p.read_bytes())
                batch.setdefault('format_retries',[]).append(attempt);store.save(r)
            copied=None
            if r['universal_plan'].get('frozen_design_run'):
                from .replay import load_draft
                draft,copied=load_draft(store,r,index)
                batch['generation_mode']='frozen-response-replay'
                batch['original_draft_ref']=store.artifact(r,f'model/batch-{index+1}-original-draft.json',copied['original_draft'])
                for retry in copied['format_retries']:
                    entry={k:v for k,v in retry['entry'].items() if not k.endswith('_ref')}
                    entry['inherited_from']=r['universal_plan']['frozen_design_run']
                    for role,raw in retry['raws'].items():entry[role+'_ref']=store.artifact(r,f'model/format-retry-{index+1}-{role}.json',raw)
                    batch.setdefault('format_retries',[]).append(entry)
            else:draft=design_draft(store,data,cancelled,preserve_rejected)
            batch.update(state='completed',draft_id=draft['id'],connection=draft['connection'],issues=draft['issues'])
            # Prefix local identities only; exact inputs, expected values and
            # quote text remain untouched and are re-projected on archive reads.
            for req in draft['requirements']:
                req=json.loads(json.dumps(req));req['id']='B'+str(index+1)+'-'+req['id']
                for c in req['cases']:c['id']='B'+str(index+1)+'-'+c['id']
                r['universal_generation']['requirements'].append(req)
            r['universal_generation']['issues']+=draft['issues']
            cid=draft['connection']['client_request_id']
            for folder,suffix in [('drafts','draft'),('model-inputs','input'),('model-responses','response'),('model-calls','receipt')]:
                name=draft['id'] if folder=='drafts' else cid
                raw=copied[suffix] if copied is not None else (store.root/folder/(name+'.json')).read_bytes()
                batch[suffix+'_ref']=store.artifact(r,f'model/batch-{index+1}-{suffix}.json',raw)
        except (ValueError,OSError) as exc:
            created=[p for p in (store.root/'model-calls').glob('*.json') if p.name not in before]
            batch.update(state='error',reason=str(exc)[:1200])
            r['universal_generation']['issues'].append(dict(kind='generation',source='batch-'+str(index+1),reason=str(exc)[:1200]))
            for receipt_path in created:
                receipt=json.loads(receipt_path.read_bytes());cid=receipt['client_request_id']
                for folder in ('model-calls','model-inputs','model-responses'):
                    p=store.root/folder/(cid+'.json')
                    if p.is_file():store.artifact(r,'model/rejected-'+str(index+1)+'-'+folder+'.json',p.read_bytes())
                partial=store.root/'model-responses'/(cid+'.partial')
                if partial.is_file():
                    require(sha(partial.read_bytes())==receipt.get('partial_response_sha256'),'模型部分响应摘要不符')
                    batch['partial_response_ref']=store.artifact_file(r,'model/rejected-'+str(index+1)+'-partial-response.bin',partial)
        r['universal_generation']['batches'].append(batch);store.save(r)
        (output/'generation.json').write_bytes(encode(batch))
        mode='frozen response recompile' if r['universal_plan'].get('frozen_design_run') else 'configured model'
        return runtime.result_file(output,[dict(name='独立文档批次已处置；覆盖缺口另行判定',status='passed')]),dict(argv=[mode,'batch',str(index+1)],exit_code=0)
    r['_source_path']=str(store.path(r['id'])/'source')
    r['_harness_path']=str(store.path(r['id'])/'universal-driver')
    r['_task_timeout']=t['timeout']
    try:
        if kind=='cleanup':return runtime.cleanup(r,output)
        if kind=='service':return runtime.service(r,runtime.unit(r,t['target']),output,cancelled,on_progress=lambda:store.save(r))
        return getattr(runtime,kind)(r,runtime.unit(r,t['target']),output,cancelled)
    finally:r.pop('_source_path',None);r.pop('_harness_path',None);r.pop('_task_timeout',None)


def completion(r):
    generation=r.get('universal_generation',{});issues=[dict(x) for x in generation.get('issues',[])]
    for t in r['tasks']:
        if t['state'] in {'error','cancelled','blocked'}:issues.append(dict(kind='execution',source=t['id'],reason=t.get('error','未执行')))
        incomplete=[x for x in t.get('report',{}).get('tests',[]) if x['status'] in {'error','skipped'}]
        if incomplete:
            if r['universal_plan'].get('execution_contract',{}).get('version',0)>=15 and t['tool']=='universal-business':
                for row in incomplete:
                    reason='该用例未完整执行，查看逐步原件'
                    try:
                        detail=json.loads(row.get('detail',''))
                        steps=detail.get('steps',{})
                        if isinstance(steps,dict):
                            first=next((s for s in [*steps.get('steps',[]),*steps.get('cleanup',[])] if s.get('status')=='error'),None)
                            if first:reason=first.get('error',reason)
                        if detail.get('checks') and any(c.get('status')=='error' for c in detail['checks']):reason='声明的观察字段或比较协议不可用'
                    except (ValueError,AttributeError):pass
                    issues.append(dict(kind='execution',source=t['id'],case=row['name'].split(' · ',1)[0],reason=row['name']+'：'+reason,observations=[{k:row[k] for k in ('name','status','message','detail') if k in row}]))
            else:issues.append(dict(kind='execution',source=t['id'],reason='部分用例未完整执行'))
    cases=[c for req in generation.get('requirements',[]) for c in req['cases']]
    if not cases:issues.append(dict(kind='coverage',source='业务用例',reason='没有通过依据校验的独立业务用例'))
    from .coverage import classify
    issues=classify(r,issues)
    return dict(kind='declared-scope',execution_complete=all(t['state'] in {'completed','error','cancelled','blocked'} for t in r['tasks']),complete=not issues and len(generation.get('batches',[]))==len(r['universal_plan']['batches']),
        missing=[str(x.get('source') or x.get('requirement') or '未定位')+'：'+x['reason'] for x in issues],gaps=issues,scope=r['universal_plan']['scope'],requirements=len(generation.get('requirements',[])),cases=len(cases))


def case_defaults(case):
    # Only a top-level optional locator has gained a default. Never normalize
    # nested input/expected values: absent keys and explicit null differ there.
    return {'entry':None,**case}


def requirement_defaults(rows):
    return [{**{'gap_category':None,**row},'cases':[case_defaults(c) for c in row['cases']]} for row in rows]


def verify_archived(store,r):
    from .generation import validate,legacy_tool_rejections
    from ..planning.verification import response_matches
    p=r['universal_plan'];require(json.loads(store.artifact_bytes_for_record(r,r['universal_plan_ref'])[1])==p,'通用方案原件不一致')
    if p.get('projection_context'):
        from .bindings import context
        require(p['projection_context']==context(p['discovery']['units']),'公开依赖绑定与冻结发现不一致')
    require(r['profile']==p['profile'] and r['context']['snapshot_digest']==p['snapshot_digest'] and r['context']['files']==p['manifest'],'通用方案输入范围不一致')
    require([{k:t[k] for k in p['profile']['tasks'][0]} for t in r['tasks']]==p['profile']['tasks'],'通用任务清单不一致')
    requirements=[];issues=list(p['gaps'])
    validator_ref=r.get('universal_drivers',{}).get('callback_contract.cjs')
    syntax_validator_sha=sha(store.artifact_bytes_for_record(r,validator_ref)[1]) if validator_ref else None
    indices=[b['index'] for b in r['universal_generation']['batches']]
    require(len(set(indices))==len(indices) and all(type(i) is int and 0<=i<len(p['batches']) for i in indices),'模型批次身份重复或越界')
    for filename,aid in r.get('universal_drivers',{}).items():
        _,raw=store.artifact_bytes_for_record(r,aid)
        require((store.path(r['id'])/'universal-driver'/filename).read_bytes()==raw,'冻结执行驱动变化')
    for b in r['universal_generation']['batches']:
        retries=b.get('format_retries',[])
        require(len(retries)<=1,'格式重试超过冻结上限')
        for retry in retries:
            receipt=json.loads(store.artifact_bytes_for_record(r,retry['model-calls_ref'])[1])
            inp=store.artifact_bytes_for_record(r,retry['model-inputs_ref'])[1]
            response=store.artifact_bytes_for_record(r,retry['model-responses_ref'])[1]
            require(receipt['client_request_id']==retry['client_request_id'] and receipt.get('state')=='rejected' and receipt.get('rejection_kind')=='json_syntax','重试来源不是已结束的格式拒绝')
            require(sha(inp)==receipt['input_sha256'] and sha(response)==receipt['response_sha256'],'重试原件摘要不符')
            if p.get('execution_contract',{}).get('version',0)>=16 and receipt.get('provider')=='deepseek':
                from ..planning.model_budget import verify as verify_budget
                verify_budget(json.loads(inp),receipt)
            original_input=json.loads(inp)['prompt'];raw_retry=json.loads(response)
            require(original_input['documents']==p['batches'][b['index']] and original_input['discovery']['execution_contract']==p['execution_contract'],'重试改变了文档或执行契约')
            require(raw_retry['choices'][0]['finish_reason']=='stop','未知终态不能重试')
            try:json.loads(raw_retry['choices'][0]['message']['content'])
            except json.JSONDecodeError:pass
            else:raise ValueError('重试原件不存在JSON语法错误')
        if b['state']=='error':issues.append(dict(kind='generation',source='batch-'+str(b['index']+1),reason=b['reason']));continue
        wrapper=json.loads(store.artifact_bytes_for_record(r,b['draft_ref'])[1]);d=wrapper['record'];require(sha(encode(d))==wrapper['sha256'],'模型草稿摘要不符')
        if d.get('syntax_evidence'):require(syntax_validator_sha is not None,'语法回执缺少冻结的校验器原件')
        raw=json.loads(store.artifact_bytes_for_record(r,b['response_ref'])[1]);require(sha(encode(raw))==d['response_sha256'] and response_matches(raw,d['connection']),'原始模型响应不一致')
        require(d['documents']==p['batches'][b['index']] and d['target']['units']==p.get('model_units',p['discovery']['units']),'模型输入不属于冻结发现与文档批次')
        if p.get('document_retrieval'):require(d['target'].get('document_scope')==p['document_retrieval']['batches'][b['index']],'模型依据范围与冻结选择不一致')
        if 'model_units' in p:require(d['target'].get('context_version')==2 and d['target'].get('execution_contract')==p['execution_contract'],'模型执行能力契约不属于冻结方案')
        selected,_=relevant(p['discovery']['interfaces'],p['batches'][b['index']],public_only=p.get('execution_contract',{}).get('version',0)>=14)
        require(d['target']['interfaces']==selected,'模型入口上下文不属于冻结语法索引')
        if p.get('execution_contract',{}).get('version',0)>=4:require(d['target'].get('types')==p['discovery'].get('types',[]),'模型类型上下文不属于冻结语法索引')
        input_raw=store.artifact_bytes_for_record(r,b['input_ref'])[1]
        if p.get('execution_contract',{}).get('version',0)>=16 and d['connection'].get('provider')=='deepseek':
            from ..planning.model_budget import verify as verify_budget
            input_wrapper=json.loads(input_raw);receipt=json.loads(store.artifact_bytes_for_record(r,b['receipt_ref'])[1])
            verify_budget(input_wrapper,receipt)
        if retries:
            previous=store.artifact_bytes_for_record(r,retries[0]['model-inputs_ref'])[1]
            if p.get('execution_contract',{}).get('version',0)>=16 and d['connection'].get('provider')=='deepseek':
                left=json.loads(input_raw);right=json.loads(previous)
                left.get('generation_budget',{}).pop('observed_at',None);right.get('generation_budget',{}).pop('observed_at',None)
                require(left==right,'格式重试改变了原始输入或预算')
            else:require(input_raw==previous,'格式重试改变了原始输入')
        require(sha(input_raw)==d['input_sha256'],'原始模型输入不一致')
        actual_input=json.loads(input_raw)['prompt']
        require(actual_input.get('discovery')==d['target'] and actual_input.get('documents')==d['documents'],'模型原始输入未绑定冻结发现与文档')
        original=json.loads(raw['choices'][0]['message']['content'])
        require(original==d['model_output'],'模型正文与草稿不一致')
        if p.get('projection_context'):require(d.get('projection_context')==p['projection_context'],'公开依赖编译上下文未绑定冻结方案')
        compiled=None
        if p.get('frozen_design_run'):
            from .replay import verify_original
            require(b.get('generation_mode')=='frozen-response-replay' and b.get('original_draft_ref'),'冻结设计来源缺失')
            require(d.get('recompiled_from',{}).get('batch')==b['index'],'冻结设计批次来源不符')
            compiled=verify_original(json.loads(store.artifact_bytes_for_record(r,b['original_draft_ref'])[1]),d,p,original,syntax_validator_sha=syntax_validator_sha)
        # Re-project the actual response, including its original object order.
        # Pydantic diagnostics include input repr; sorted storage is not input.
        rows,local,anchors=compiled if compiled is not None else validate(original,[Document.model_validate(x) for x in d['documents']],d['target'],projection_context=d.get('projection_context'),syntax_evidence=d.get('syntax_evidence'),validator_sha=syntax_validator_sha,tool_rejections=legacy_tool_rejections(d))
        require(requirement_defaults(rows)==requirement_defaults(d['requirements']) and local==d['issues'] and anchors==d['citations'],'模型用例投影或引用与归档复核不一致；需区分校验未完成与数据改变')
        for req in rows:
            req['id']='B'+str(b['index']+1)+'-'+req['id']
            for c in req['cases']:c['id']='B'+str(b['index']+1)+'-'+c['id']
            requirements.append(req)
        issues+=local
    require(requirement_defaults(requirements)==requirement_defaults(r['universal_generation']['requirements']) and issues==r['universal_generation']['issues'],'执行预期与已冻结模型原件不一致')
    if p.get('execution_contract',{}).get('version',0)>=15:
        from .environment import verify_selection
        verify_selection(store,r)
    if p.get('execution_contract',{}).get('version',0)>=19:
        for task in r['tasks']:
            if task['tool']!='universal-service' or task['state']!='completed':continue
            u=runtime.unit(r,task['target']);nodes=u.get('service_graph',{}).get('nodes',[])
            if not nodes:continue
            artifact=next((a for a in r['artifacts'] if a['name']==task['id']+'/graph.json'),None)
            require(artifact is not None,'多服务图运行原件缺失')
            actual=json.loads(store.artifact_bytes_for_record(r,artifact['id'])[1])
            require(actual==r.get('universal_graphs',{}).get(u['id']),'多服务路由状态与运行原件不符')
            require([n['id'] for n in actual]==[n['id'] for n in nodes],'多服务运行图与冻结发现不符')
            for node,ran in zip(nodes,actual):
                require(all(ran.get(k)==v for k,v in node.items() if k!='argv'),'多服务节点声明被改变')
                if node.get('argv'):require(ran.get('argv')==node['argv']+['--pool=solo','--concurrency=1','--hostname=acceptance@'+u['id']] or ran['status']=='error' and ran.get('argv')==node['argv'],'worker命令与冻结声明不符')
                require(ran['container']==runtime.names(r,u)[0]+'-'+node['id'],'服务容器不属于该组件')
    if p.get('execution_contract',{}).get('version',0)>=20:
        for uid,bases in r.get('universal_bases',{}).items():
            for base in bases:
                candidates=[a for a in r['artifacts'] if a['name'].startswith((uid+'-prepare/',uid+'-build/')) and a['name'].endswith('/baseline.json')]
                matched=[a for a in candidates if json.loads(store.artifact_bytes_for_record(r,a['id'])[1])==base]
                require(len(matched)==1 and base['source_digest']==p['snapshot_digest'],'业务环境基线与准备/构建原件不符')
                owner=next(t for t in r['tasks'] if t['id']==matched[0]['name'].split('/')[0])
                native=next((t for t in r['tasks'] if t['target']==uid and t['tool']=='universal-native' and t.get('started_at')),None)
                require(not native or owner.get('finished_at') and owner['finished_at']<=native['started_at'],'业务基线继承了原生测试后的状态')
    for task in r['tasks']:
        if task['tool']!='universal-business' or task['state']!='completed':continue
        cases=[c for req in requirements for c in req['cases'] if c['unit']==task['target']]
        expected={c['id']+' · '+c['title'] for c in cases};actual=[x['name'] for x in task['report']['tests']]
        require(len(actual)==len(expected) and set(actual)==expected,'业务执行结果未覆盖全部冻结用例')
        artifact=next((a for a in r['artifacts'] if a['name']==task['id']+'/cases.json'),None)
        require(artifact is not None,'逐用例步骤证据缺失')
        traces=json.loads(store.artifact_bytes_for_record(r,artifact['id'])[1]);require([case_defaults(x['case']) for x in traces]==[case_defaults(c) for c in cases],'实际执行输入或预期与冻结模型用例不符')
        require([x['status'] for x in traces]==[x['status'] for x in task['report']['tests']],'逐用例状态与原生报告不符')
        if p.get('execution_contract',{}).get('version',0)>=20:
            for trace in traces:
                if trace['status']=='error':continue
                environment=trace.get('environment',{});case=trace['case'];prefix=task['id']+'/'+case['id']+'/environment/environment.json'
                saved=next((a for a in r['artifacts'] if a['name']==prefix),None)
                require(saved is not None and json.loads(store.artifact_bytes_for_record(r,saved['id'])[1])==environment,'用例独立环境原件缺失或改变')
                require(environment.get('removed') is True and environment.get('case_id')==case['id'] and environment.get('base') in {b['volume'] for b in r.get('universal_bases',{}).get(task['target'],[])},'用例未使用已冻结的独立环境或未清理')
                if p.get('fixture_preparation_version'):
                    prepared=r.get('universal_fixture_preparation',{}).get(task['target'],{});selection=prepared.get('cases',{}).get(case['id'])
                    if selection:
                        group=prepared.get('groups',{}).get(selection.get('key'),{});actual=environment.get('fixture_preparation',{})
                        require(group.get('state')=='ready' and actual.get('key')==selection['key'] and actual.get('volume')==group['volume'] and actual.get('mount_readonly') is True,'业务未使用已准备的只读构建夹具缓存')
        if p.get('execution_contract',{}).get('version',0)>=18:
            for trace in traces:
                case=trace['case']
                if case['kind']!='journey' or trace['status']=='error':continue
                prefix=task['id']+'/'+case['id']+'/'
                files={a['name'][len(prefix):]:a for a in r['artifacts'] if a['name'].startswith(prefix)}
                require({'browser-request.json','trace.zip','network.har','session-final.json','journey-result.json'}<=files.keys(),'浏览器流程原件不完整')
                raw=json.loads(store.artifact_bytes_for_record(r,files['browser-request.json']['id'])[1])
                require(raw['steps']==case['journey']['steps'],'浏览器实际输入或预期不属于冻结模型用例')
                receipt=trace['actual'];steps=receipt['steps'];ids=[s['id'] for s in case['journey']['steps']]
                require([s['id'] for s in steps]==ids[:len(steps)],'浏览器步骤顺序与冻结流程不符')
                require(receipt.get('session_cleanup',{}).get('status')=='completed' and receipt.get('resources_removed') is True,'浏览器应用没有完整清理')
                if trace['status']=='passed':require(len(steps)==len(ids) and all(s['status']=='passed' for s in steps),'浏览器只执行了部分步骤')
    from .fixture_preparation import verify_archived as verify_fixtures
    verify_fixtures(store,r)
    if p.get('remote_source'):
        from ..remote import verify_archived as verify_remote
        verify_remote(store,{**r,'test_plan':p})
    return True


def present(view,r,store=None):
    p=r['universal_plan'];stages=[dict(id='discovery',title='仓库发现',status='passed',detail=f"{len(p['discovery']['units'])} 个组件；{p['discovery']['interface_count']} 个公开函数；{len(p['documents'])} 份文档，按片段批次读取")]
    for item in p.get('stages',STAGES)[1:]:
        tids={n['id'] for n in p['dag'] if n['stage']==item['id']};tasks=[t for t in r['tasks'] if t['id'] in tids]
        if not tasks:continue
        states={t['state'] for t in tasks};status='running' if 'running' in states else 'queued' if 'queued' in states else 'blocked' if states&{'error','cancelled','blocked'} else 'failed' if any(any(x['status']=='failed' for x in t.get('report',{}).get('tests',[])) or t.get('report',{}).get('findings') for t in tasks) else 'passed'
        if status=='passed' and (any(x['status'] in {'skipped','error'} for t in tasks for x in t.get('report',{}).get('tests',[])) or item['id']=='design' and r.get('universal_generation',{}).get('issues')):status='blocked'
        stages.append(dict(id=item['id'],title=item['title'],status=status,detail=f"{sum(t['state']=='completed' for t in tasks)}/{len(tasks)} 项已执行；局部问题不阻止其他分支",check_ids=list(tids),duration_ms=sum(t.get('duration_ms') or 0 for t in tasks)))
        starts=[t['started_at'] for t in tasks if t.get('started_at')];ends=[t['finished_at'] for t in tasks if t.get('finished_at')]
        if starts:stages[-1]['started_at']=min(starts)
        if ends and not states&{'running','queued'}:stages[-1]['finished_at']=max(ends)
        for c in view['baseline']['criteria']:
            if c['id'] in tids:c['layer']=item['id']
        for row in view['results']:
            if row['criterion_id'] in tids:row['layer']=item['id']
    extra=[s for s in view['display_stages'] if s['id'] in {'review','gate'}]
    for stage in extra:
        if stage['id']=='gate' and stage['status']=='error' and r['decision']=='inconclusive' and any(x['name']=='质量门禁' and x['state']=='completed' for x in r['pipeline']):stage['status']='blocked'
    allstages=stages+extra;generation=r.get('universal_generation',{});coverage=completion(r)
    view.update(pipeline=allstages,display_stages=allstages,stages=allstages,completion=coverage,universal_plan={**public(p,sha(encode(p))),**generation,'issues':coverage['gaps'],'service_runs':r.get('universal_graphs',{}),'fixture_preparation':r.get('universal_fixture_preparation',{})},reasons=[p['scope']],limits=coverage['missing'])
    models=[b['connection']['actual_model'] for b in generation.get('batches',[]) if b.get('connection')]
    view['source']['tooling']['model']=', '.join(sorted(set(models))) or None
    if store:
        traces=[]
        business={t['id'] for t in r['tasks'] if t['tool']=='universal-business'}
        for artifact in r['artifacts']:
            if artifact['name'].endswith('/cases.json') and artifact['name'].split('/')[0] in business:
                traces+=json.loads(store.artifact_bytes_for_record(r,artifact['id'])[1])
        view['universal_plan']['executions']=traces
    view['test_plan']=None
    return view
