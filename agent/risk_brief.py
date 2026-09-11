from __future__ import annotations
import json
import pandas as pd
from .deepseek_client import chat as deepseek_chat

PATH_CN={'WS':'水压力（WS）','DR':'历史干旱（DR）','SV':'季节波动（SV）'}

def _fmt(x, n=4):
    try: return f'{float(x):.{n}f}'
    except Exception: return str(x)

def baseline_brief(result: dict, material: str|None=None) -> str:
    if not result or result.get('data') is None:
        return '当前没有可解释的 Baseline 结果。请先上传可计算的采购数据。'
    s=result['data']['summary']; n=result['data']['nodes']
    if isinstance(s,list): s=pd.DataFrame(s)
    if isinstance(n,list): n=pd.DataFrame(n)
    if material and not s.empty and material in set(s.material):
        s=s[s.material==material]; n=n[n.material==material]
    paras=[]
    for _,r in s.iterrows():
        mat=r.material; gn=n[n.material==mat]
        topc=gn.sort_values('C',ascending=False).iloc[0] if len(gn) else None
        topr=gn.sort_values('R',ascending=False).iloc[0] if len(gn) else None
        paths={'WS':float(r.path_contrib_WS or 0),'DR':float(r.path_contrib_DR or 0),'SV':float(r.path_contrib_SV or 0)}
        dom=max(paths,key=paths.get); ptotal=sum(paths.values()) or 1
        coverage=float(r.get('scored_coverage', r.get('Coverage', 0)) or 0)
        procurement=float(r.get('Coverage',0) or 0)
        lines=[f'### {mat} 当前水风险分析',
               f'- **PRWI**：{_fmt(r.PRWI)}；采购覆盖率 {procurement*100:.1f}%，可评分覆盖率 {coverage*100:.1f}%；风险区间 [{_fmt(r.PRWI_lower)}, {_fmt(r.PRWI_upper)}]。',
               f'- **主要风险驱动**：{PATH_CN[dom]}，约占当前路径贡献的 {paths[dom]/ptotal*100:.1f}%。']
        if topc is not None:
            lines.append(f'- **企业优先关注节点**：{topc.node_name}（{topc.node_id}），贡献 C={_fmt(topc.C)}，约占组合贡献 {float(topc.contribution_share or 0)*100:.1f}%。')
        if topr is not None:
            lines.append(f'- **节点自身风险较高**：{topr.node_name}（{topr.node_id}），R={_fmt(topr.R)}。' + (' 它与最高贡献节点不同，说明采购权重会改变企业层面的优先级。' if topc is not None and topr.node_id!=topc.node_id else ''))
        lines.append('- **数据与证据边界**：请同时查看 Unknown、Proxy/Assumption、Confidence 与来源。示范采购结构不得表述为真实企业采购敞口。')
        lines.append('- **建议**：优先核验高贡献节点的真实采购份额与供应连续性；对高风险节点强化水风险监测，并结合库存和替代来源开展压力测试。')
        paras.append('\n'.join(lines))
    fallback='\n\n'.join(paras)
    # Supply the deterministic summary as text; DeepSeek may reorganize language but may not add numbers.
    sys=(
        '你是企业水风险决策助手。以下所有数字来自确定性程序。严格保持数字原值，不新增、不重算、不猜测。'
        '请把内容整理成面向企业用户的简洁中文分析，区分：程序结论、数据/情景假设、管理建议。'
        '不要把PRWI解释为损失概率或财务损失。'
    )
    text, _meta = deepseek_chat(sys, fallback, fallback)
    return text

def scenario_brief(result: dict) -> str:
    if not result or result.get('data') is None:
        return '当前没有可解释的 Scenario 结果。'
    d=result['data']; typ=d.get('scenario_type')
    if typ in ['PeakSeason','ExtremeDrought']:
        delta=float(d['PRWI_delta']); direction='上升' if delta>0 else ('下降' if delta<0 else '不变')
        title='当前峰值季节' if typ=='PeakSeason' else '历史极端干旱'
        fallback=(f'### {title}压力测试\n- Baseline PRWI={_fmt(d["PRWI_baseline"])}，情景 PRWI={_fmt(d["PRWI_scenario"])}，ΔPRWI={_fmt(delta)}，风险指数{direction}。\n'
                  '- 该结果用于压力测试，不代表未来发生概率。\n- 应结合节点级变化、数据身份、Confidence 与情景参数判断风险是否发生转移。')
    elif typ=='AqueductFuture':
        fallback=(f'### Aqueduct Future 情景\n- {d.get("year")} / {d.get("path")}：Baseline PRWI={_fmt(d.get("PRWI_baseline"))}，未来情景 PRWI={_fmt(d.get("PRWI_future"))}，ΔPRWI={_fmt(d.get("PRWI_delta"))}。\n'
                  '- 当前 Future 数据若标记为 Demo/S 类，只能用于流程与敏感性演示，不能包装为确定预测。')
    elif typ=='NodeFailure':
        fallback=(f'### 核心节点失效情景\n- 失效节点：{d.get("target_node_name")}（{d.get("target_node_id")}），失效比例={float(d.get("failure_fraction_f",0))*100:.0f}%。\n'
                  f'- Gross Loss={_fmt(d.get("gross_loss"))}，库存使用={_fmt(d.get("inventory_used"))}，替代供应={_fmt(d.get("replacement_allocated"))}，未满足需求={_fmt(d.get("unmet_demand"))}。\n'
                  f'- Conditional PRWI={_fmt(d.get("conditional_PRWI"))}；采购 HHI={_fmt(d.get("procurement_hhi"))}，风险 HHI={_fmt(d.get("risk_hhi"))}。\n'
                  '- 风险质量下降不等于企业更安全；必须同时看未满足需求、替代能力和集中度。')
    else:
        fallback='Scenario 结果已生成，请查看结构化输出。'
    if result.get('warnings'):
        fallback += '\n- **情景边界**：' + '；'.join(result['warnings'])
    sys=(
        '你是企业水风险决策助手。严格忠实于给定Scenario确定性结果，不创造任何新数字。'
        '不得将压力测试写成预测，不得创造财务损失或断供概率。请输出简洁中文，并把程序结论和管理建议分开。'
    )
    text, _meta=deepseek_chat(sys, fallback, fallback)
    return text

def data_audit_brief(validation: dict) -> str:
    if not validation: return '尚未完成数据校验。'
    out=[f'### 数据检查：{validation.get("status","unknown")}']
    cov=validation.get('coverage',{})
    if isinstance(cov,dict): out.append('- 采购覆盖：'+'；'.join(f'{k} {float(v)*100:.1f}%' for k,v in cov.items()))
    for title,key in [('需要确认','issues'),('提示','warnings'),('数据缺口','data_gaps')]:
        vals=validation.get(key,[])
        if vals: out.append(f'- **{title}**：'+'；'.join(map(str,vals)))
    out.append('- Unknown 不等于 0；未确认的关键企业字段不会自动进入正式计算。')
    return '\n'.join(out)
