/* Isomorphic, pure safety calculations. No network calls, no secrets. */
(function(root,factory){const api=factory(); if(typeof module==='object'&&module.exports)module.exports=api;root.GovernanceCore=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const STATES=['已核实','待验证','规划能力','最终决策'];
const TABS=[
 ['cloud','迁云方案','比选主机、参考费用、区域、网络路径和内网访问边界。'],
 ['architecture','CompanyAgent / Hermes 架构','按 Runtime、Broker、Gateway、KMS、PEP 与审计责任边界维护能力清单。'],
 ['mcp','IAH 与 MCP 接入','维护服务与工具、最小 scope、租户隔离、审计和接口健康。'],
 ['imds','IMDS 合规 PoC','按证据记录用例、性能和已知局限；合成测试不代表真实数据验收。'],
 ['security','风险与安全边界','API Key、SecretRef、IAM、KMS、VPC、代理、白名单与关键安全控制。'],
 ['gates','验证门禁','验收条款、执行状态、失败证据和阻断规则。'],
 ['migration','迁移进度','追踪 Shadow Mode、迁云试点、失败原因、回滚条件和负责人。'],
 ['decisions','待确认决策','将事实、假设和审批决策严格分开记录。'],
 ['reports','汇报材料','自动整理风险、决策对比、导师/同事消息与可复制摘要。']
];
const SCHEMAS={
 cloud:[['provider','平台'],['plan','实例/方案'],['region','区域'],['cost','月费用参考'],['network','网络/流量'],['boundary','内部访问边界'],['evidence','证据/来源'],['state','证据状态']],
 architecture:[['component','组件'],['design','架构职责'],['boundary','安全职责/边界'],['gate','验收要求'],['state','证据状态']],
 mcp:[['service','服务'],['tools','工具/接口'],['scopes','权限范围'],['tenant','租户隔离'],['audit','审计要求'],['health','接口健康'],['state','证据状态']],
 imds:[['metric','验证项目'],['result','历史结果/目标'],['basis','数据范围'],['limitation','局限与后续'],['state','证据状态']],
 security:[['control','安全检查项'],['requirement','核验要求'],['status','检查结果'],['owner','负责人/系统'],['evidence','验证依据'],['state','证据状态']],
 gates:[['gate','验收门禁'],['criteria','通过标准'],['status','运行结果'],['failure','失败原因/阻断项'],['rollback','失败/回滚条件'],['evidence','证据'],['state','证据状态']],
 migration:[['task','迁移任务'],['phase','阶段'],['status','进展'],['owner','责任人'],['failure','失败原因'],['rollback','回滚条件'],['acceptance','验收标准'],['state','证据状态']],
 decisions:[['question','待决策事项'],['options','备选方案'],['owner','审批人/团队'],['impact','风险/影响'],['status','决策状态'],['evidence','依据/补充条件'],['state','证据状态']]
};
const seed=()=>({version:1,updated:'2026-11-21',records:{
cloud:[
 {provider:'AWS',plan:'Lightsail 4 GB（公开任务试点）',region:'us-west-2 / us-east-1 待实测',cost:'约 USD 24/月（历史估算，待官网核价）',network:'静态 IPv4；实际出口、延迟与区域可用性待测',boundary:'仅公开任务；禁止直连公司内网 API',evidence:'前期调研方案；未完成选区实测',state:'待验证'},
 {provider:'AWS',plan:'EC2 + VPC 企业隔离',region:'与公司企业网络对齐',cost:'未核定；需列实例、NAT、流量和日志费用',network:'VPC、PrivateLink/VPN/专线按实际批准方案选型',boundary:'内部 API 需企业许可、最小权限及出口控制',evidence:'目标架构规划，不代表企业 VPC 已开通',state:'规划能力'},
 {provider:'Railway',plan:'v1.7 食品饮料合成公网演示（Caddy + FastAPI 单容器）',region:'尚未选择 Railway 区域',cost:'尚未开通项目；按 Railway 账单实际核算',network:'Railway HTTPS 域名 → 认证 Caddy → 127.0.0.1:8765',boundary:'无企业真实数据、无红豆 API Token、无对内 API；仅合成展示',evidence:'GitHub Actions #44899511956：单镜像认证/403/健康检查 PASS；Railway 账号未连接、项目未创建',state:'已核实'},
 {provider:'Azure / Google Cloud',plan:'候选对照',region:'北美待选',cost:'待核价',network:'连通性与公司合规审查待验证',boundary:'未批准接入任何企业内部 API',evidence:'备选平台，未完成对照试验',state:'待验证'}],
architecture:[
 {component:'Hermes Agent Runtime',design:'承载任务执行、工具编排及失败记录',boundary:'Runtime 不直接持有长期高权限凭证',gate:'隔离执行、超时/重试/幂等与失败注入',state:'规划能力'},
 {component:'Model Broker + KMS',design:'模型路由、预算、访问控制和短期秘密获取',boundary:'身份隔离；KMS 故障默认拒绝',gate:'密钥轮换、审计、故障降级和出口校验',state:'规划能力'},
 {component:'Tool Gateway + PDP/PEP',design:'精确工具与参数授权、外发审批、执行审计',boundary:'仅白名单工具；拒绝身份/租户注入',gate:'参数越权、SSRF、未授权访问负向测试',state:'规划能力'},
 {component:'Migration Adapter + Shadow Mode',design:'任务快照/对照、对称回滚与旧平台并跑',boundary:'先公开只读 Cron，后评估高风险任务',gate:'连续观测、误差阈值、明确回滚负责人',state:'规划能力'}],
mcp:[
 {service:'IAH IMDS 合规复核 MCP（设计）',tools:'submit_imds_review / get_imds_review_status / get_imds_review_result',scopes:'review:submit / review:read 按主体授予',tenant:'tenant + subject + scopes 逐请求校验',audit:'batch_id 幂等；审计不记录材料原文与凭证',health:'未进行生产连通验证',state:'待验证'},
 {service:'本地 Streamable HTTP PoC',tools:'POST /mcp；本机开发端口 8766',scopes:'默认拒绝未授权工具',tenant:'跨租户负向测试待留证',audit:'请求 ID、耗时、结果状态；禁止敏感明文日志',health:'历史设计/PoC记录，未现场复测',state:'待验证'}],
imds:[
 {metric:'规则与追溯单元测试',result:'历史记录 14/14',basis:'合成 BOM / 规则样例',limitation:'本轮尚未复测，不能据此宣称真实手顺覆盖',state:'待验证'},
 {metric:'合成数据包',result:'76 节点 BOM、19 节点综合样例',basis:'模拟数据',limitation:'真实 CSV、异常表与字段冲突需端到端核验',state:'待验证'},
 {metric:'微基准（历史记录）',result:'中位数 0.7654 / 0.2382 / 0.0481 ms（300 次）',basis:'小规模微基准',limitation:'不代表 1 万行或完整 HTTP/LLM 性能；需补 p95/p99',state:'待验证'},
 {metric:'真实数据验收',result:'未完成',basis:'需公司授权的脱敏测试包',limitation:'多候选、缺 Node ID、规则缺失、追溯超层均需 needs_review',state:'规划能力'}],
security:[
 {control:'API Key 与日志',requirement:'服务端存放；禁止前端/仓库/Prompt/日志明文；轮换与权限审计',status:'待验证',owner:'运行平台管理员',evidence:'未收到生产密钥或部署验收证据',state:'待验证'},
 {control:'SecretRef',requirement:'引用不等同加密保险柜；确认实际持久化位置和加密方式',status:'待验证',owner:'OpenClaw 管理员',evidence:'此前官方文档核验结论；部署环境待检查',state:'待验证'},
 {control:'KMS / IAM',requirement:'最小权限、短期凭证、轮换、失效默认拒绝；不假设 Lightsail 可挂实例角色',status:'未通过',owner:'云平台责任人',evidence:'缺企业授权和目标环境验证',state:'规划能力'},
 {control:'VPC / 内网 API',requirement:'内部 API 不直接经公开实例访问；企业批准后通过私有网络与策略网关',status:'阻断',owner:'企业安全与网络团队',evidence:'没有公司网络连通及授权证明',state:'待验证'},
 {control:'代理、出站白名单',requirement:'限定 DNS/域名/IP、禁止云元数据泄露及 HTTP 隧道绕过',status:'待验证',owner:'网络管理员',evidence:'尚无实际 egress 测试',state:'待验证'},
 {control:'Skill / MCP 供应链',requirement:'来源校验、固定版本/Hash、审批与沙箱；拒绝自修改持久化规则',status:'待验证',owner:'平台安全审核',evidence:'需要负向测试与审计快照',state:'规划能力'}],
gates:[
 {gate:'公开 Cron 稳定性门禁',criteria:'北美试点连续运行、失败重试和任务结果一致',status:'待验证',failure:'云主机尚未部署并实测',rollback:'任意重复/漏执行或 SLA 越限，切回旧调度',evidence:'暂无现场云上执行记录',state:'待验证'},
 {gate:'网络隔离与权限门禁',criteria:'最小权限、出口白名单、零内网直连、敏感信息负向测试',status:'未通过',failure:'企业内部 API 尚未获授权',rollback:'任何越权/密钥泄露立即禁用连接',evidence:'缺授权、流量与审计记录',state:'待验证'},
 {gate:'IAH / MCP 端到端门禁',criteria:'授权、租户隔离、幂等、超时、错误映射及审计全通过',status:'待验证',failure:'仅有设计及 PoC 记录',rollback:'接口不健康即停止提交，保留人工审核',evidence:'待提供测试执行 ID',state:'待验证'},
 {gate:'IMDS 真实数据门禁',criteria:'规则映射、异常分支、万行性能及人工复核逐项留证',status:'待验证',failure:'当前只掌握合成测试历史记录',rollback:'需要人工复核的结果不可自动 Approve / Reject',evidence:'待测试包/人工样例',state:'待验证'},
 {gate:'模型 Tool Calling 实联调（合成数据）',criteria:'授权 TokenDance API Key + 实际 tool_calls + 三类只读工具',status:'通过',failure:'deepseek-v3.2 曾 HTTP 403，原因未确定；glm-5.2 已通过',rollback:'超权限/非法参数/模型异常一律拒绝并回退确定性方案',evidence:'GitHub Actions #44896062819，glm-5.2 实网 3 tools，脱敏 artifact #14703494776',state:'已核实'},
 {gate:'云端合成镜像与隔离',criteria:'非 root 镜像、回环绑定、旧版 API 禁用、无企业 Key/数据',status:'通过',failure:'仅 GitHub Runner 单次容器验证；AWS 企业网络尚未部署',rollback:'任意公开端口或企业凭据注入即拒绝启动',evidence:'Cloud synthetic container smoke #44896850328；不等于 AWS 生产验收',state:'已核实'},
 {gate:'Railway 公网演示部署验收',criteria:'授权云账户、随机双层密码、Railway HTTPS 域名、401/403/健康检查、费用限额',status:'待验证',failure:'仅 Docker 镜像 CI 通过，Railway 连接与外网实际部署尚未完成',rollback:'撤下 Railway 域名或停止服务，删除临时数据并轮换凭据',evidence:'Railway image CI #44899511956；非实际 Railway 部署',state:'待验证'},
 {gate:'企业真实数据接入审批',criteria:'数据所有者+安全负责人审批、数据范围、留存与审计',status:'未通过',failure:'无真实数据授权、企业 SSO 与租户隔离证据',rollback:'不得上传/同步真实企业数据；转离线校验与人工审批',evidence:'enterprise/ingress_review.py 仅校验离线摘要，不进行实际写入',state:'待验证'}],
migration:[
 {task:'冻结 OpenClaw 任务清单与依赖',phase:'准备',status:'进行中',owner:'迁移负责人',failure:'任务/密钥/网络依赖尚未完整盘点',rollback:'原运行环境与调度配置保持可恢复',acceptance:'清单审签；Cron / API / 内网依赖分类',state:'待验证'},
 {task:'GitHub 云端合成容器验证',phase:'Cloud CI 验证',status:'已完成（合成数据）',owner:'项目 CI',failure:'尚无实际 AWS VPC 资源与真实业务负载',rollback:'不对公网开放，变更不通过即销毁临时容器',acceptance:'Cloud synthetic Docker smoke #44896850328，旧 API 和导入入口返回403',state:'已核实'},
 {task:'Railway 食品饮料公网合成演示',phase:'演示部署',status:'代码与 CI 完成；等待账号连接',owner:'Railway 账户所有者',failure:'没有 Railway 连接/授权、域名与实际账单证据',rollback:'取消公网域名并停止服务，容器临时数据不保留',acceptance:'真实 *.up.railway.app HTTPS 地址、401/403、健康检查与独立登录证据',state:'待验证'},
 {task:'Lightsail 北美公开任务试点',phase:'公开任务试点',status:'未开始',owner:'云平台负责人',failure:'主机/网络/成本实测待安排',rollback:'失败即恢复旧 Cron，避免双活重复执行',acceptance:'真实连续运行与对照日志',state:'规划能力'},
 {task:'CompanyAgent / Hermes Shadow Mode',phase:'双轨验证',status:'未开始',owner:'Agent 平台负责人',failure:'尚未达到治理负向门禁',rollback:'禁写与流量切回 OpenClaw',acceptance:'同输入同结果；工具权限与审计匹配',state:'规划能力'},
 {task:'公司内部 API 接入',phase:'独立隔离验收',status:'阻断',owner:'企业安全责任人',failure:'没有正式网络及数据访问授权',rollback:'默认保持未连接；撤销临时凭证',acceptance:'授权审批、隔离测试、审计、应急预案完整',state:'待验证'}],
decisions:[
 {question:'公开任务试点选型',options:'Lightsail 4 GB / EC2 小规格 / Azure / Google Cloud',owner:'项目负责人',impact:'费用、区域、运行稳定性及网络延迟',status:'待确认',evidence:'需要实际价格和北美连通性对照',state:'待验证'},
 {question:'Railway 演示服务创建和费用权限',options:'Railway 账户连接 → 新项目 → GitHub main 根 Dockerfile → 加密 Variables → 生成 HTTPS 域名',owner:'Railway 项目所有者',impact:'需防止费用超限及错误公网暴露；仅限合成数据',status:'待确认',evidence:'代码与 Docker CI 已完成；没有实际 Railway 部署或账单',state:'待验证'},
 {question:'内部 API 的云上访问方式',options:'继续企业现有环境 / EC2 + 企业 VPC + 经批准网络链路',owner:'企业网络与安全审批人',impact:'最高风险：数据外发与跨网边界',status:'未决定',evidence:'禁止在批准前开放生产内网访问',state:'待验证'},
 {question:'CompanyAgent 替换旧平台验收窗口',options:'公开只读任务 Shadow Mode → 审计评审 → 分批切流',owner:'平台负责人',impact:'任务重复、漏执行、密钥与回滚责任',status:'未决定',evidence:'需书面门禁通过报告',state:'规划能力'}]
}});
const clone=o=>JSON.parse(JSON.stringify(o));
function redact(s){return String(s==null?'':s).replace(/\bsk-[A-Za-z0-9_-]{8,}\b/g,'[REDACTED_KEY]').replace(/Bearer\s+[A-Za-z0-9._~+/-]{8,}/gi,'Bearer [REDACTED]').replace(/(api[_ -]?key|secret|token|password)\s*[:=]\s*[^\s,;，；]{6,}/gi,'$1=[REDACTED]');}
function forbidden(s){return /\bsk-[A-Za-z0-9_-]{8,}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|Bearer\s+[A-Za-z0-9._~+/-]{8,}/i.test(String(s));}
function validateRecord(type,record){if(!SCHEMAS[type]||!record||typeof record!=='object'||Array.isArray(record))throw Error('记录类型非法');const out={};for(const [key] of SCHEMAS[type]){const val=record[key]??'';if(typeof val!=='string'||val.length>600)throw Error('字段类型或长度非法');if(forbidden(val))throw Error('检测到疑似密钥；禁止导入或保存真实凭证');out[key]=val;}if(out.state&&!STATES.includes(out.state))throw Error('证据状态必须采用四态分类');return out;}
function sanitizeImport(input){if(!input||input.version!==1||!input.records||typeof input.records!=='object')throw Error('导入格式不兼容');const result=seed();for(const type of Object.keys(SCHEMAS)){if(!Array.isArray(input.records[type])||input.records[type].length>300)throw Error(type+' 必须是最多300条记录的数组');result.records[type]=input.records[type].map(x=>validateRecord(type,x));}return result;}
function riskItems(data){const r=data.records;const risk=[];const add=(level,title,why)=>risk.push({level,title,why});
if(r.security.some(x=>/VPC|内网/.test(x.control)&&x.status!=='通过'))add('高','内网访问边界未过门禁','企业内部 API 尚不可从公开云主机直连；须审批网络、身份和数据范围。');
if(r.security.some(x=>/API Key|SecretRef|KMS/.test(x.control)&&x.status!=='通过'))add('高','密钥与身份治理未完成','不可仅凭 SecretRef 或环境变量名称假设秘密获得加密与权限保护。');
if(r.gates.some(x=>x.status==='未通过'||x.status==='失败'))add('高','至少一项验收门禁失败','禁止将当前原型标记为生产可用或自动切流。');
if(r.mcp.some(x=>!/已验证健康/.test(x.health)))add('中','MCP 接口健康尚无实测证据','需补身份、租户、超时、审计和端到端健康检查。');
if(r.imds.some(x=>/真实数据/.test(x.metric)&&x.result==='未完成'))add('中','IMDS 缺少真实数据验收','合成测试只能证明特定规则与输入，不能替代真实手顺和万行验证。');
if(r.gates.some(x=>/Tool Calling/.test(x.gate)&&x.status!=='通过'))add('中','模型工具真实联调待完成','密钥缺席时只能报告 Mock 协议验证，不能声称线上成功。');
if(r.migration.some(x=>x.status==='阻断'))add('高','迁移任务存在阻断','保留旧系统与回滚路径；不得强行扩权绕过。');
return risk;}
function metrics(data){const r=data.records;const risks=riskItems(data);return{controls:r.security.length,tasks:r.migration.length,gatesOpen:r.gates.filter(x=>x.status!=='通过').length,risks:risks.length,decisions:r.decisions.filter(x=>x.status!=='已批准').length};}
function report(data,audience='mentor'){const m=metrics(data);const risk=riskItems(data);const prefix=audience==='colleague'?'各位同事好：':'您好！';const migration=data.records.migration.map(x=>`${x.task}（${x.status}）`).join('、');const gate=data.records.gates.filter(x=>x.status!=='通过').map(x=>x.gate).join('、');const decisions=data.records.decisions.filter(x=>x.status!=='已批准').map(x=>x.question).join('、');const liveModelVerified=data.records.gates.some(x=>/模型 Tool Calling/.test(x.gate)&&x.status==='通过'&&x.state==='已核实');const modelNote=liveModelVerified?'已证实 TokenDance glm-5.2 在合成数据上完成真实只读 Tool Calling，但不代表企业真实数据或生产环境已验收。':'尚未证实真实模型 Tool Calling；不得将 Mock 测试当作线上通过。';return `${prefix}\n\n同步 CompanyAgent 安全治理与 OpenClaw 迁云的阶段进展。当前已建立 ${m.controls} 项安全检查、${m.tasks} 条迁移任务与 ${data.records.gates.length} 项验证门禁。进度：${migration}。\n\n关键边界保持不变：公开只读任务可以先在北美云主机做稳定性试点；公司内部 API 与敏感数据在正式授权、私有网络和最小权限验收前不得接入。${gate?'未通过/待验证的门禁包括：'+gate+'。':''}\n\n自动整理的主要风险：${risk.map(x=>x.title).join('、')}。当前需要确认：${decisions}。\n\n说明：历史合成测试与公开仓库 CI 不等同真实业务数据验收；${modelNote}下一步建议先补齐选型实测、执行证据与回滚演练，经评审后再推进。\n\n以上为工作台记录自动汇总，发送前请核对最新状态。`;}
return {STATES,TABS,SCHEMAS,seed,clone,redact,forbidden,validateRecord,sanitizeImport,riskItems,metrics,report};
});