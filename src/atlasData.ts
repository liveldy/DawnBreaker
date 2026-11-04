// @ts-nocheck
// Adapted from liveldy/last-token model-atlas (GPL-3.0); see third_party/NOTICE.md.
// DawnBreaker changes: official links, live-feed validation, metadata matching and display fields.
/* ==========================================================================
   模型能力图鉴 · 数据集构建
   --------------------------------------------------------------------------
   这个文件同时被两边加载：
     · 浏览器   —— <script src="data/model-data.js">，挂到 window.ModelData
     · Node     —— tools/build-data.cjs require 它来生成快照
   因此用最朴素的写法：没有 import / export。

   数据来源（都是公开接口）：
     · ZeroEval / LLM Stats  api.zeroeval.com
         /leaderboard/indexes/all   —— general 等分类的综合能力（TrueSkill μ − 3σ）
         /leaderboard/models/full   —— 模型元数据：日期、上下文、参数量、协议、标价、各基准分
     · OpenRouter             openrouter.ai/api/v1/models —— 缺价时的兜底
   ========================================================================== */

const ModelData = (function () {
  'use strict';

  /* ---------- 1. 图上画多少名 ---------- */

  /* 能力图只画综合能力最高的这一批；没有公开标价的会被跳过（列在图的页脚里）。 */
  var PLOT_LIMIT = 50;

  /* ---------- 2. 厂商配色 ----------
     图上每个点按厂商上色。固定表覆盖掉常见的二十来个厂商，其余用名字散列出一个稳定的色相，
     这样同一个厂商在任何一次构建里都是同一个颜色。 */

  var ORG_COLORS = {
    anthropic:   '#e0733d',
    openai:      '#10a37f',
    google:      '#4285f4',
    meta:        '#7c5cff',
    deepseek:    '#4f86f7',
    qwen:        '#a855f7',
    xai:         '#f2c14e',
    mistral:     '#ef6f6c',
    bytedance:   '#22c1c3',
    moonshotai:  '#8ab4f8',
    'zai-org':   '#14b8a6',
    perplexity:  '#0ea5e9',
    tencent:     '#3fb950',
    minimax:     '#ec4899',
    microsoft:   '#5b9bd5',
    nvidia:      '#76b900',
    amazon:      '#ff9900',
    xiaomi:      '#ff6900',
    ibm:         '#5b8def',
    cohere:      '#d946ef',
    meituan:     '#f5c518',
    stepfun:     '#38bdf8',
    reflection:  '#94a3b8',
    baidu:       '#4f7cff',
    alibaba:     '#a855f7',
    apple:       '#9ca3af',
    ai21:        '#f97316',
    databricks:  '#ff3621',
    nousresearch:'#c084fc',
    allenai:     '#7dd3fc'
  };

  /* 没在表里的厂商：由 id 散列出 60°~300° 的色相，避开太黄/太绿的区间 */
  var FALLBACK_HUES = [12, 32, 48, 168, 190, 205, 222, 245, 268, 288, 312, 336];

  function orgColor(orgId) {
    if (ORG_COLORS[orgId]) return ORG_COLORS[orgId];
    var h = 0;
    var s = String(orgId || '?');
    for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 100003;
    var hue = FALLBACK_HUES[h % FALLBACK_HUES.length];
    return 'hsl(' + hue + ' 62% 58%)';
  }

  /* ---------- 3. 基准分字段 ----------
     统一取 models/full 里 0~1 的那批分数，尺度一致、能横向比；
     分类里 benchmark_results 收录的更多条数只用来显示“收录几条”。 */

  var BENCHMARKS = [
    { key: 'gpqa_score', name: 'GPQA Diamond', zh: '研究生级科学问答' },
    { key: 'hle_score', name: 'Humanity\'s Last Exam', zh: '跨学科专家难题' },
    { key: 'aime_2025_score', name: 'AIME 2025', zh: '竞赛数学' },
    { key: 'frontiermath_score', name: 'FrontierMath', zh: '前沿数学研究题' },
    { key: 'swe_bench_verified_score', name: 'SWE-bench Verified', zh: '真实仓库修 bug' },
    { key: 'swe_bench_pro_score', name: 'SWE-bench Pro', zh: '更难的软件工程任务' },
    { key: 'scicode_score', name: 'SciCode', zh: '科学计算代码' },
    { key: 'terminal_bench_score', name: 'Terminal-Bench', zh: '终端实操' },
    { key: 'arc_agi_v2_score', name: 'ARC-AGI v2', zh: '抽象推理' },
    { key: 'mcp_atlas_score', name: 'MCP Atlas', zh: '工具调用' },
    { key: 'toolathlon_score', name: 'Toolathlon', zh: '多工具长流程' },
    { key: 'tau_bench_retail_score', name: 'τ-bench Retail', zh: '客服代理对话' },
    { key: 'apex_agents_score', name: 'APEX Agents', zh: '代理任务' },
    { key: 'browsecomp_score', name: 'BrowseComp', zh: '联网检索' },
    { key: 'simpleqa_score', name: 'SimpleQA', zh: '事实性短问答' },
    { key: 'osworld_score', name: 'OSWorld', zh: '桌面操作' },
    { key: 'mmmu_score', name: 'MMMU', zh: '多模态理解' },
    { key: 'mmmu_pro_score', name: 'MMMU-Pro', zh: '多模态理解（难）' },
    { key: 'mmmlu_score', name: 'MMMLU', zh: '多语言知识' },
    { key: 'charxiv_r_score', name: 'CharXiv-R', zh: '图表推理' },
    { key: 'screenspot_pro_score', name: 'ScreenSpot-Pro', zh: '界面定位' },
    { key: 'mrcr_v2_score', name: 'MRCR v2', zh: '长上下文检索' }
  ];

  /* ---------- 4. 参考成本的示例工作量 ----------
     和图上的横轴口径一致：输入 : 输出 = 3 : 1 加权。
     中文按经验值 1 token ≈ 1.5 个汉字换算。 */

  var WORKLOADS = [
    { id: 'chat', label: '一次长对话', tokensIn: 20000, tokensOut: 4000, note: '读约 3 万汉字，写约 6 千字' },
    { id: 'doc', label: '一份长报告', tokensIn: 200000, tokensOut: 20000, note: '读约 30 万汉字，写约 3 万字' },
    { id: 'bulk', label: '批量跑 100 万 tokens 输入', tokensIn: 1000000, tokensOut: 200000, note: '大规模离线推理' }
  ];

  var SOURCES = {
    index: {
      name: 'ZeroEval / LLM Stats · general 指数',
      url: 'https://api.zeroeval.com/leaderboard/indexes/all',
      proxy: '/api/zeroeval/leaderboard/indexes/all',
      note: '综合能力：TrueSkill 保守估计（μ − 3σ），同一标尺下的全局排名'
    },
    models: {
      name: 'ZeroEval / LLM Stats · 模型元数据',
      url: 'https://api.zeroeval.com/leaderboard/models/full',
      proxy: '/api/zeroeval/leaderboard/models/full',
      note: '版本、发布日期、上下文、参数量、开源协议、官方标价与各基准分'
    },
    openrouter: {
      name: 'OpenRouter · 模型价格',
      url: 'https://openrouter.ai/api/v1/models',
      proxy: '/api/openrouter/v1/models',
      note: 'ZeroEval 未给标价时的兜底来源'
    }
  };

  /* ---------- 5. 小工具 ---------- */

  function num(v) {
    return (typeof v === 'number' && isFinite(v)) ? v : null;
  }

  function round(v, d) {
    var f = Math.pow(10, d == null ? 2 : d);
    return Math.round(v * f) / f;
  }

  function normKey(s) {
    return String(s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  }

  /* 参考成本：每百万 token 的加权美元价，输入:输出 = 3:1（与 TokenDance 榜口径一致） */
  function costOf(priceIn, priceOut) {
    if (priceIn === null || priceOut === null) return null;
    return round((3 * priceIn + priceOut) / 4, 4);
  }

  function benchList(model) {
    var out = [];
    for (var i = 0; i < BENCHMARKS.length; i++) {
      var b = BENCHMARKS[i];
      var s = num(model[b.key]);
      if (s === null || s < 0 || s > 1) continue;
      out.push({ key: b.key, name: b.name, zh: b.zh, pct: round(s * 100, 1) });
    }
    return out;
  }

  /* ZeroEval 的 general 分类里每条基准的原始记录。
     尺度各不相同（有的 0~1，有的上千），所以只保留“分数 + 在几家里排第几”，
     不做横向比较。字段名压短，是为了快照别太大。 */
  function recordList(results) {
    var out = [];
    for (var k in results) {
      if (!Object.prototype.hasOwnProperty.call(results, k)) continue;
      var r = results[k];
      if (!r) continue;
      var o = num(r.of), rk = num(r.rank);
      // src 缺省即 "self_reported"（占绝大多数），不写进快照，省一百来 KB
      var src = r.source && r.source !== 'self_reported' ? r.source : null;
      out.push({
        n: r.name || k,
        s: num(r.score),
        r: rk,
        o: o,
        src: src
      });
    }
    out.sort(function (a, b) {
      var ar = a.r === null ? 1e9 : a.r, br = b.r === null ? 1e9 : b.r;
      if (ar !== br) return ar - br;
      return (b.o === null ? 0 : b.o) - (a.o === null ? 0 : a.o);
    });
    return out;
  }

  /* ---------- 6. 构建数据集 ----------
     @param {Array}  modelsFull  /leaderboard/models/full 的数组
     @param {Object} indexesAll  /leaderboard/indexes/all 的对象
     @param {Array}  openRouter  /api/v1/models 的 data 数组（可缺省）
     @param {Number} plotLimit   图上画多少名，默认 50 */
  function buildDataset(modelsFull, indexesAll, openRouter, plotLimit) {
    var limit = plotLimit || PLOT_LIMIT;
    var general = (indexesAll && indexesAll.general && indexesAll.general.models) || [];

    // 按保守估计从高到低排名次
    var seenIds = Object.create(null);
    var ranked = general.filter(function(g){return g && typeof g.model_id === 'string' && g.model_id && num(g.conservative) !== null;}).sort(function (a, b) { return b.conservative - a.conservative; }).filter(function(g){if(seenIds[g.model_id])return false;seenIds[g.model_id]=true;return true;});
    var rankOf = Object.create(null);
    for (var i = 0; i < ranked.length; i++) {
      if (!(ranked[i].model_id in rankOf)) rankOf[ranked[i].model_id] = i + 1;
    }

    var metaById = Object.create(null);
    for (var j = 0; j < modelsFull.length; j++) {
      var mm = modelsFull[j];
      if (!(mm.model_id in metaById)) metaById[mm.model_id] = mm;
    }

    // OpenRouter 兜底价：按“去掉一切非字母数字后的名字”匹配，同名只留第一条
    var orByName = Object.create(null);
    function priceKey(key,model){key=normKey(key);if(!key)return;if(!(key in orByName))orByName[key]=model;else if(orByName[key]!==model)orByName[key]=null;}
    for (var k = 0; k < (openRouter || []).length; k++) {
      var om = openRouter[k];if(!om || typeof om.id !== 'string')continue;
      priceKey(om.id,om);priceKey(om.name,om);
      // Exact provider-stripped aliases only; ambiguous names deliberately remain unpriced.
      priceKey(om.id.split('/').pop(),om);
      if(typeof om.name==='string' && om.name.indexOf(': ')>0)priceKey(om.name.slice(om.name.indexOf(': ')+2),om);
    }
    function orPrice(name) {
      var m = orByName[normKey(name)];if(!m)return null;
      var p=m.pricing||{},a=Number(p.prompt),b=Number(p.completion);
      if(p.prompt==null||p.prompt===''||p.completion==null||p.completion===''||!isFinite(a)||!isFinite(b)||a<0||b<0)return null;
      return {in:round(a*1e6,4),out:round(b*1e6,4),model:m};
    }

    var models = ranked.map(function (g) {
      var meta = metaById[g.model_id] || {};
      var priceIn = num(meta.input_price);if(priceIn!==null&&priceIn<0)priceIn=null;
      var priceOut = num(meta.output_price);if(priceOut!==null&&priceOut<0)priceOut=null;
      var from = (priceIn !== null && priceOut !== null) ? 'zeroeval' : null;
      var orInfo = null;

      if (from === null) {
        orInfo = orPrice(g.model_name);
        if (orInfo) { priceIn = orInfo.in; priceOut = orInfo.out; from = 'openrouter'; }
      }

      var results = g.benchmark_results || {};
      var benchCount = Object.keys(results).length;

      return {
        id: g.model_id,
        name: g.model_name || g.model_id,
        org: g.organization_id,
        website: ({anthropic:'https://www.anthropic.com/claude',openai:'https://openai.com',google:'https://deepmind.google/models/gemini/',meta:'https://muse.ai',deepseek:'https://www.deepseek.com',moonshotai:'https://www.kimi.com',moonshot:'https://www.kimi.com',zhipuai:'https://bigmodel.cn',zhipu:'https://bigmodel.cn',xai:'https://x.ai',alibaba:'https://qwen.ai',xiaomi:'https://mimo.xiaomi.com',minimax:'https://www.minimaxi.com',tencent:'https://hunyuan.tencent.com',baidu:'https://yiyan.baidu.com',bytedance:'https://seed.bytedance.com',meituan:'https://longcat.chat'})[String(g.organization_id||'').toLowerCase().replace(/[^a-z]/g,'')] || (/^https:\/\//.test(meta.url||meta.website||'')?(meta.url||meta.website):null),
        orgName: g.organization_name || g.organization_id,
        rank: rankOf[g.model_id],
        score: round(g.conservative, 2),
        mu: num(g.mu)===null?null:round(g.mu, 2),
        sigma: num(g.sigma)===null?null:round(g.sigma, 2),
        games: num(g.games_played),
        coverage: num(g.coverage_ratio),
        delta: num(g.rank_delta_14d),
        priceIn: priceIn,
        priceOut: priceOut,
        cost: costOf(priceIn, priceOut),
        priceFrom: from,
        context: num(meta.context) || (orInfo && num(orInfo.model.context_length)) || null,
        params: num(meta.params),
        license: meta.license || null,
        isMoe: !!meta.is_moe,
        multimodal: !!(meta.multimodal || (orInfo && orInfo.model.architecture && (orInfo.model.architecture.input_modalities || []).length > 1)),
        released: meta.release_date || null,
        announced: meta.announcement_date || null,
        cutoff: meta.knowledge_cutoff || null,
        benchmarks: benchList(meta),
        records: recordList(results),
        benchCount: benchCount
      };
    });

    // 有公开标价的模型（已按名次排好）——能力图就是从这份名单里从前往后取
    var withCostIds = models.filter(function (m) { return m.cost !== null; })
      .map(function (m) { return m.id; });

    // 默认取前 N 个上表；名次更靠前却没标价的单独列出来
    var plottedIds = withCostIds.slice(0, limit);
    var rankById = Object.create(null);
    models.forEach(function (m) { rankById[m.id] = m.rank; });
    var lastRank = plottedIds.length ? rankById[plottedIds[plottedIds.length - 1]] : 0;
    var skipped = models.filter(function (m) { return m.cost === null && m.rank < lastRank; })
      .map(function (m) { return { id: m.id, name: m.name, org: m.org, rank: m.rank }; });

    var withoutPrice = models.length - withCostIds.length;

    return {
      snapshotAt: new Date().toISOString(),
      total: models.length,
      plotLimit: limit,
      withCostIds: withCostIds,
      plottedIds: plottedIds,
      skipped: skipped,
      withoutPrice: withoutPrice,
      topScore: models.length ? models[0].score : null,
      lowScore: models.length ? models[models.length - 1].score : null,
      sources: SOURCES,
      benchmarks: BENCHMARKS,
      workloads: WORKLOADS,
      models: models
    };
  }

  /* ---------- 7. 对外 ---------- */

  var api = {
    PLOT_LIMIT: PLOT_LIMIT,
    ORG_COLORS: ORG_COLORS,
    BENCHMARKS: BENCHMARKS,
    WORKLOADS: WORKLOADS,
    SOURCES: SOURCES,
    orgColor: orgColor,
    costOf: costOf,
    buildDataset: buildDataset
  };

  return api;

}());
export default ModelData;
