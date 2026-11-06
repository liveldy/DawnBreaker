"""Read-only xAI team billing, using a separate management credential.

Contract: https://docs.x.ai/developers/rest-api-reference/management/billing
Never submits billing mutations or treats billing items as API requests.
"""
import math
from datetime import datetime,timedelta,timezone
from urllib.parse import quote
from fastapi import HTTPException

def finite(value):
    result=float(value)
    if not math.isfinite(result):raise ValueError('non-finite metric')
    return result

def statistics(team,key,request,report):
    base='https://management-api.x.ai/v1/billing/teams/'+quote(team,safe='')
    headers={'Authorization':'Bearer '+key}
    try:
        balance=request(base+'/prepaid/balance',headers=headers)
        # Credit additions are negative ledger entries (official response example).
        report.update(balance=-finite(balance['total']['val'])/100,currency='USD',balance_label='团队预付余额')
    except HTTPException as error:report['errors'].append('xAI 管理余额：'+str(error.detail))
    except (ValueError,TypeError,KeyError):report['errors'].append('xAI 管理余额返回格式变化，未显示估算值')
    end=datetime.now(timezone.utc);start=end-timedelta(days=30)
    def query(names,groups):
        body={'analyticsRequest':{'timeRange':{'startTime':start.strftime('%Y-%m-%d %H:%M:%S'),'endTime':end.strftime('%Y-%m-%d %H:%M:%S'),'timezone':'Etc/GMT'},'timeUnit':'TIME_UNIT_DAY','values':[{'name':name,'aggregation':'AGGREGATION_SUM'} for name in names],'groupBy':groups,'filters':[]}}
        data=request(base+'/usage',body=body,headers=headers)
        if data.get('limitReached'):raise HTTPException(502,'统计达到行数上限，未显示不完整合计')
        if not isinstance(data.get('timeSeries'),list):raise ValueError('missing timeSeries')
        totals=[0.0]*len(names)
        for series in data['timeSeries']:
            if groups:
                group=series['group']
                if not isinstance(group,list) or not group:raise ValueError('missing unit type')
                if 'token' not in str(group[0]).lower():continue
            for point in series['dataPoints']:
                values=point['values']
                if len(values)!=len(names):raise ValueError('incomplete metrics')
                for index,value in enumerate(values):
                    metric=finite(value)
                    if names[index]!='usd' and metric<0:raise ValueError('negative units')
                    totals[index]+=metric
        return totals
    try:
        spent,requests=query(['usd','transactions'],[])
        report.update(spent=spent,requests=int(requests),currency='USD',spent_label='团队近 30 天费用',usage_scope='团队近30天，非当前推理密钥；未含税费 / 充值')
    except HTTPException as error:report['errors'].append('xAI 管理用量：'+str(error.detail))
    except (ValueError,TypeError,KeyError):report['errors'].append('xAI 管理用量返回格式变化，未显示估算值')
    try:report['tokens']=int(query(['units'],['unit_type'])[0])
    except HTTPException as error:report['errors'].append('xAI Token 用量：'+str(error.detail))
    except (ValueError,TypeError,KeyError):report['errors'].append('xAI Token 用量返回格式变化，未将图片数 / 音频秒数当作 Token')
