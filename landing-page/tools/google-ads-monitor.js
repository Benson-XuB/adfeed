(function () {
  "use strict";

  var CUT = "2026-08-17";
  var TROAS_TARGET = 200;
  var TROAS_REF = 747;
  var DAILY_BUDGET = 18.0;
  var data = [];
  var filter = "all";
  var charts = {};
  var manualNotify = true;
  var mode = "demo";

  function $(id) { return document.getElementById(id); }

  function setBadge() {
    var el = $("dataBadge");
    if (!el) return;
    if (mode === "live") {
      el.textContent = "Live account";
      el.classList.add("gam-badge-live");
      el.classList.remove("gam-badge-demo");
    } else {
      el.textContent = "Sample data";
      el.classList.add("gam-badge-demo");
      el.classList.remove("gam-badge-live");
    }
  }

  async function loadStatus() {
    try {
      var res = await fetch("/api/public/google-ads/status", { credentials: "include" });
      var s = await res.json();
      var connect = $("connectBtn");
      var notice = $("setupNotice");
      if (notice) {
        notice.textContent = s.ads_api_configured
          ? (s.connected ? "Google Ads connected." : "Connect Google Ads (read-only) to load a live account.")
          : (s.setup_hint || "Connect Google Ads to load a live (or Test) account; Show sample works anytime.");
      }
      if (connect) {
        connect.hidden = !s.oauth_configured;
        connect.href = "/api/public/google-ads/oauth/start";
      }
      var disc = $("disconnectBtn");
      if (disc) disc.hidden = !s.connected;
      if (s.connected && s.ads_api_configured) {
        await loadCustomers();
      }
      return s;
    } catch (e) {
      return null;
    }
  }

  async function loadCustomers() {
    var sel = $("customerSelect");
    if (!sel) return;
    try {
      var res = await fetch("/api/public/google-ads/customers", { credentials: "include" });
      var data = await res.json();
      sel.innerHTML = "";
      (data.customers || []).forEach(function (c) {
        var opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.id;
        sel.appendChild(opt);
      });
      sel.hidden = !(data.customers || []).length;
      var loadBtn = $("loadLiveBtn");
      if (loadBtn) loadBtn.hidden = !(data.customers || []).length;
    } catch (e) {}
  }

  async function loadReport(opts) {
    opts = opts || {};
    var url = "/api/public/google-ads/demo";
    var qs = new URLSearchParams({
      cut: CUT,
      daily_budget: String(DAILY_BUDGET),
      troas_target: String(TROAS_TARGET),
    });
    if (opts.live && opts.customerId) {
      url = "/api/public/google-ads/report?" + new URLSearchParams({
        customer_id: opts.customerId,
        date_from: opts.dateFrom || "2026-08-01",
        date_to: opts.dateTo || "2026-08-31",
        cut: CUT,
        daily_budget: String(DAILY_BUDGET),
        troas_target: String(TROAS_TARGET),
      }).toString();
    } else {
      url = "/api/public/google-ads/demo?" + qs.toString();
    }
    var res = await fetch(url, { credentials: "include" });
    var payload = await res.json();
    if (!res.ok) throw new Error(payload.detail || "Failed to load report");
    mode = payload.mode || "demo";
    CUT = payload.cut || CUT;
    DAILY_BUDGET = payload.daily_budget || DAILY_BUDGET;
    TROAS_TARGET = payload.troas_target || TROAS_TARGET;
    data = (payload.rows || []).slice();
    var note = $("reportNotice");
    if (note) {
      note.textContent = payload.notice || "";
      note.hidden = !payload.notice;
    }
    setBadge();
    if (typeof renderAll === "function") renderAll();
  }

  /* ===== 派生指标 ===== */
  function enrich(r){
    return {
      d:r.d, imp:r.imp, clk:r.clk, spd:r.spd, cvn:r.cvn, cvv:r.cvv,
      ctr: r.imp>0 ? r.clk/r.imp*100 : 0,
      cpc: r.clk>0 ? r.spd/r.clk : 0,
      roas: r.spd>0 ? r.cvv/r.spd*100 : 0,
      lim: r.spd >= DAILY_BUDGET * 0.97
    };
  }
  function agg(rows){
    var e = rows.map(enrich);
    var n = e.length||1;
    var s = {
      imp:e.reduce(function(a,b){return a+b.imp;},0),
      clk:e.reduce(function(a,b){return a+b.clk;},0),
      spd:e.reduce(function(a,b){return a+b.spd;},0),
      cvn:e.reduce(function(a,b){return a+b.cvn;},0),
      cvv:e.reduce(function(a,b){return a+b.cvv;},0),
      limDays:e.filter(function(r){return r.lim;}).length,
      n:rows.length
    };
    s.ctr = s.imp>0 ? s.clk/s.imp*100 : 0;
    s.cpc = s.clk>0 ? s.spd/s.clk : 0;
    s.roas = s.spd>0 ? s.cvv/s.spd*100 : 0;
    s.avgImp = s.imp/n;
    s.avgClk = s.clk/n;
    s.avgCvn = s.cvn/n;
    return s;
  }
  function split(rows){
    var pre=[],post=[];
    rows.forEach(function(r){ (r.d>=CUT?post:pre).push(r); });
    return {pre:pre, post:post};
  }

  /* ===== 格式化 ===== */
  function fmtInt(v){ return Math.round(v).toLocaleString('en-US'); }
  function fmtMoney(v){ return '$'+Number(v).toFixed(2); }
  function fmtPct(v){ return Number(v).toFixed(1)+'%'; }
  function fmtDelta(cur,base){
    if(!base) return '';
    return ((cur-base)/base*100);
  }
  function deltaClass(v){
    if(v===null||v===undefined||isNaN(v)) return 'n';
    return v>0 ? 'b' : (v<0 ? 'g' : 'n');
  }
  function deltaArrow(v){
    if(v>0.5) return '↑';
    if(v<-0.5) return '↓';
    return '→';
  }

  /* ===== KPI ===== */
  function kpiCard(lbl, val, deltaHtml, per){
    return '<div class="kpi"><div class="lbl">'+lbl+'</div><div class="val">'+val+'</div>'+
      (deltaHtml?'<div class="dlt">'+deltaHtml+'</div>':'')+
      (per?'<div class="per">'+per+'</div>':'')+'</div>';
  }
  function renderKPIs(){
    var rows = filter==='all' ? data : (filter==='pre' ? split(data).pre : split(data).post);
    var a = agg(rows);
    var sp = split(data);
    var preA = agg(sp.pre), postA = agg(sp.post);
    var lbl = filter==='all' ? '整体' : (filter==='pre' ? '8/17 前' : '8/17 后');

    function d(cur,base,f,goodDown){
      var v = fmtDelta(cur,base);
      var cls = deltaClass(goodDown ? -v : v);
      return '<span class="'+cls+'">'+(v>0?'+':'')+Number(v).toFixed(0)+'% · 前 '+f(base)+' → 后 '+f(cur)+'</span>';
    }
    function c1(x){ return fmtInt(x); }
    function c2(x){ return fmtMoney(x); }
    function c3(x){ return Number(x).toFixed(1); }

    var html = '';
    html += kpiCard('展示（'+lbl+'）', fmtInt(a.imp), d(postA.avgImp, preA.avgImp, c1, true), '日均 '+fmtInt(a.avgImp));
    html += kpiCard('点击（'+lbl+'）', fmtInt(a.clk), d(postA.avgClk, preA.avgClk, c1, true), '日均 '+fmtInt(a.avgClk));
    html += kpiCard('CTR（'+lbl+'）', fmtPct(a.ctr), d(postA.ctr, preA.ctr, fmtPct, true), '点击率');
    html += kpiCard('CPC（'+lbl+'）', fmtMoney(a.cpc), d(postA.cpc, preA.cpc, c2, false), '单次点击成本');
    html += kpiCard('花费（'+lbl+'）', fmtMoney(a.spd), d(postA.spd, preA.spd, c2, false), '日预算 $' + Number(DAILY_BUDGET).toFixed(2));
    html += kpiCard('转化（'+lbl+'）', fmtInt(a.cvn), d(postA.avgCvn, preA.avgCvn, c3, true), '日均 '+c3(a.avgCvn));
    html += kpiCard('ROAS（'+lbl+'）', fmtPct(a.roas), d(postA.roas, preA.roas, fmtPct, true), '目标 tROAS '+TROAS_TARGET+'%');
    html += kpiCard('预算状态（'+lbl+'）', a.limDays===a.n ? '预算受限' : (a.limDays+'/'+a.n+' 天受限'), '', a.n+' 天中 '+a.limDays+' 天花满预算');
    document.getElementById('kpis').innerHTML = html;
  }

  /* ===== 前后对比 ===== */
  function renderComparison(){
    var sp = split(data);
    var preA = agg(sp.pre), postA = agg(sp.post);
    function row(name, preStr, postStr, delta, cls){
      return '<div class="cmp-row"><div class="cmp-name">'+name+'</div>'+
        '<div class="cmp-pre">'+preStr+'</div><div class="cmp-arrow">→</div>'+
        '<div class="cmp-post">'+postStr+'</div>'+
        '<div class="cmp-delta '+cls+'">'+(delta>0?'+':'')+Number(delta).toFixed(0)+'%</div></div>';
    }
    function dlt(cur,base){ return ((cur-base)/base)*100; }
    var html = '';
    html += row('日均展示', fmtInt(preA.avgImp), fmtInt(postA.avgImp), dlt(postA.avgImp,preA.avgImp), deltaClass(-dlt(postA.avgImp,preA.avgImp)));
    html += row('日均点击', fmtInt(preA.avgClk), fmtInt(postA.avgClk), dlt(postA.avgClk,preA.avgClk), deltaClass(-dlt(postA.avgClk,preA.avgClk)));
    html += row('平均 CPC', fmtMoney(preA.cpc), fmtMoney(postA.cpc), dlt(postA.cpc,preA.cpc), deltaClass(dlt(postA.cpc,preA.cpc)));
    html += row('日均花费', fmtMoney(preA.spd/ preA.n), fmtMoney(postA.spd/postA.n), dlt(postA.spd/postA.n, preA.spd/preA.n), 'n');
    html += row('日均转化', Number(preA.avgCvn).toFixed(1), Number(postA.avgCvn).toFixed(1), dlt(postA.avgCvn,preA.avgCvn), deltaClass(-dlt(postA.avgCvn,preA.avgCvn)));
    html += row('ROAS', fmtPct(preA.roas), fmtPct(postA.roas), dlt(postA.roas,preA.roas), deltaClass(-dlt(postA.roas,preA.roas)));
    document.getElementById('cmpBody').innerHTML = html;
  }

  /* ===== 影响信号 ===== */
  function renderSignals(){
    var sp = split(data);
    var preA = agg(sp.pre), postA = agg(sp.post);
    var cpcDelta = (postA.cpc-preA.cpc)/preA.cpc*100;
    var clkDelta = (postA.avgClk-preA.avgClk)/preA.avgClk*100;
    var s1 = cpcDelta >= 50;
    var s2 = clkDelta <= -30;
    var s3 = postA.limDays === postA.n;
    function sig(name, state, cls, extra){
      return '<div class="sig-row"><span class="sig-dot '+cls+'"></span><span class="sig-name">'+name+'</span>'+
        '<span class="sig-state '+cls+'">'+state+'</span>'+(extra||'')+'</div>';
    }
    var html = '';
    html += sig('CPC 较更新前上升 ≥50%', '当前 '+fmtPct(cpcDelta), s1?'hit':'ok');
    html += sig('日均点击较更新前下降 ≥30%', '当前 '+Number(clkDelta).toFixed(0)+'%', s2?'hit':'ok');
    html += sig('更新后预算仍花满（受限）', postA.limDays+'/'+postA.n+' 天', s3?'hit':'ok');
    html += '<div class="sig-check"><input type="checkbox" id="notifyChk" '+(manualNotify?'checked':'')+'><label for="notifyChk">收到谷歌「Review your campaign targets」提示</label></div>';
    var hits = (s1?1:0)+(s2?1:0)+(s3?1:0)+(manualNotify?1:0);
    var result, cls;
    if(hits>=3){ result = '高度疑似受 8/17 更新影响'; cls=''; }
    else if(hits===2){ result = '部分信号命中，需结合账户通知确认'; cls=''; }
    else { result = '暂未见明显影响信号'; cls=' green'; }
    var sug = '建议：把 tROAS 设定值与「8/17 前实际 ROAS」的差距收窄（谷歌 Bid Target Adjustment Tool 可直接参考），改后等 1–2 个完整转化周期再评估；本示例中谷歌工具参考值为 '+TROAS_REF+'%，设定目标 '+TROAS_TARGET+'%。';
    html += '<div class="sig-result'+cls+'"><div class="head">判定：'+result+'（'+hits+'/4 项命中）</div><div class="sug">'+sug+'</div></div>';
    document.getElementById('signalsBody').innerHTML = html;
    var chk = document.getElementById('notifyChk');
    if(chk){ chk.addEventListener('change', function(){ manualNotify = chk.checked; renderSignals(); }); }
  }

  /* ===== ECharts ===== */
  function initChart(id){
    if(typeof echarts==='undefined') return null;
    var el = document.getElementById(id);
    if(!el) return null;
    var c = echarts.init(el);
    if(!charts[id]){
      charts[id] = c;
      if(typeof ResizeObserver!=='undefined'){
        new ResizeObserver(function(){ c.resize(); }).observe(el);
      }
    }
    return c;
  }
  function baseOpt(){
    return {
      backgroundColor:'transparent',
      tooltip:{trigger:'axis',confine:true,backgroundColor:'#FFFFFF',borderColor:'#E4E3DD',textStyle:{color:'#1A1B1C',fontSize:11}},
      legend:{type:'scroll',bottom:0,textStyle:{color:'#6B7280',fontSize:11}},
      textStyle:{fontFamily:'Noto Sans SC, PingFang SC, Microsoft YaHei, sans-serif'}
    };
  }
  var CUT_INDEX = null;
  function renderTrend(){
    var c = initChart('trendChart');
    if(!c) return;
    var e = data.map(enrich);
    var labels = e.map(function(r){ return r.d.slice(5).replace('-','/'); });
    CUT_INDEX = e.findIndex(function(r){ return r.d>=CUT; });
    c.setOption(Object.assign(baseOpt(),{
      grid:{left:54,right:56,top:34,bottom:44,containLabel:false},
      xAxis:{type:'category',data:labels,boundaryGap:false,
        axisLine:{lineStyle:{color:'#D5D3CB'}},axisTick:{show:false},
        axisLabel:{color:'#6B7280',fontSize:11,interval:'auto'}},
      yAxis:[
        {type:'value',name:'展示 / 点击',nameTextStyle:{color:'#9AA0A6',fontSize:10},
          splitLine:{lineStyle:{color:'#ECEBE5'}},
          axisLabel:{color:'#6B7280',fontSize:11,formatter:function(v){ return v>=1000 ? (v/1000)+'k' : v; }}},
        {type:'value',name:'CPC ($)',nameTextStyle:{color:'#9AA0A6',fontSize:10},
          splitLine:{show:false},
          axisLabel:{color:'#6B7280',fontSize:11,formatter:function(v){ return '$'+v.toFixed(2); }}}
      ],
      series:[
        {name:'展示',type:'line',yAxisIndex:0,data:e.map(function(r){return r.imp;}),smooth:true,symbol:'none',
          lineStyle:{width:1.5,color:'#9EC7F8'},
          areaStyle:{color:'#4285F4',opacity:0.08}},
        {name:'点击',type:'line',yAxisIndex:0,data:e.map(function(r){return r.clk;}),smooth:true,symbol:'none',
          lineStyle:{width:2,color:'#4285F4'}},
        {name:'CPC',type:'line',yAxisIndex:1,data:e.map(function(r){return +r.cpc.toFixed(3);}),smooth:true,symbol:'none',
          lineStyle:{width:2,color:'#EA6668'}},
        {name:'8/17 更新',type:'line',data:[],markLine:{silent:true,symbol:['none','none'],
          lineStyle:{color:'#EA6668',type:'dashed',width:1},
          label:{formatter:'8/17 更新',color:'#EA6668',fontSize:11,position:'insideEndTop'},
          data:[{xAxis:CUT_INDEX}]}}
      ]
    }),true);
  }
  function renderRoas(){
    var c = initChart('roasChart');
    if(!c) return;
    var e = data.map(enrich);
    var labels = e.map(function(r){ return r.d.slice(5).replace('-','/'); });
    c.setOption(Object.assign(baseOpt(),{
      grid:{left:54,right:20,top:34,bottom:44,containLabel:false},
      xAxis:{type:'category',data:labels,boundaryGap:false,
        axisLine:{lineStyle:{color:'#D5D3CB'}},axisTick:{show:false},
        axisLabel:{color:'#6B7280',fontSize:11,interval:'auto'}},
      yAxis:{type:'value',name:'ROAS (%)',nameTextStyle:{color:'#9AA0A6',fontSize:10},
        splitLine:{lineStyle:{color:'#ECEBE5'}},
        axisLabel:{color:'#6B7280',fontSize:11,formatter:function(v){ return v+'%'; }}},
      series:[
        {name:'实际 ROAS',type:'line',data:e.map(function(r){return +r.roas.toFixed(1);}),smooth:true,symbol:'none',
          lineStyle:{width:2,color:'#4285F4'},
          areaStyle:{color:'#4285F4',opacity:0.08},
          markLine:{silent:true,symbol:['none','none'],
            data:[
              {yAxis:TROAS_TARGET,lineStyle:{color:'#FAAD14',type:'dashed',width:1.5},
                label:{formatter:'tROAS 目标 '+TROAS_TARGET+'%',color:'#8C5A00',fontSize:11,position:'insideEndTop'}},
              {yAxis:TROAS_REF,lineStyle:{color:'#52C41A',type:'dashed',width:1},
                label:{formatter:'谷歌工具 8/17 前实际 '+TROAS_REF+'%',color:'#2E7D32',fontSize:11,position:'insideStartTop'}},
              {xAxis:CUT_INDEX,lineStyle:{color:'#EA6668',type:'dashed',width:1},
                label:{formatter:'8/17',color:'#EA6668',fontSize:11,position:'insideEndTop'}}
            ]}}
      ]
    }),true);
  }

  /* ===== 明细表 ===== */
  function renderTable(){
    var head = ['日期','展示','点击','CTR','CPC','花费','转化','转化价值','ROAS','预算状态'];
    var html = '<tr>';
    head.forEach(function(h){ html += '<th>'+h+'</th>'; });
    html += '</tr>';
    document.getElementById('tableHead').innerHTML = html;
    var body = '';
    data.forEach(function(r){
      var e = enrich(r);
      var post = r.d>=CUT;
      if(r.d===CUT){
        body += '<tr class="split-row"><td colspan="10">—— 2026-08-17 智能出价更新分界 ——</td></tr>';
      }
      body += '<tr class="'+(post?'post-row':'')+'">'+
        '<td>'+r.d+'</td><td>'+fmtInt(r.imp)+'</td><td>'+fmtInt(r.clk)+'</td>'+
        '<td>'+fmtPct(e.ctr)+'</td><td>'+fmtMoney(e.cpc)+'</td><td>'+fmtMoney(e.spd)+'</td>'+
        '<td>'+r.cvn+'</td><td>'+fmtMoney(r.cvv)+'</td><td>'+fmtPct(e.roas)+'</td>'+
        '<td><span class="budget '+(e.lim?'lim':'ok')+'">'+(e.lim?'预算受限':'正常')+'</span></td></tr>';
    });
    document.getElementById('tableBody').innerHTML = body;
  }

  /* ===== 数据操作 ===== */
  function normalizeDate(s){
    if(/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
    if(/^\d{1,2}-\d{1,2}$/.test(s)){
      var p=s.split('-');
      return '2026-'+String(+p[0]).padStart(2,'0')+'-'+String(+p[1]).padStart(2,'0');
    }
    return null;
  }
  function parseCsv(text){
    var lines = text.split(/\r?\n/).map(function(s){return s.trim();}).filter(Boolean);
    if(!lines.length) throw '没有可解析的行';
    var start=0;
    var first = lines[0].split(',');
    if(isNaN(+first[1]) || /日/.test(first[0])){
      start=1;
      if(lines.length<2) throw '只有表头，没有数据行';
    }
    var out=[];
    for(var i=start;i<lines.length;i++){
      var p=lines[i].split(',').map(function(s){return s.trim();});
      if(p.length<6) throw '第'+(i+1)+'行字段不足：需要 日期,展示,点击,花费,转化数,转化价值（共 6 列）';
      var d=normalizeDate(p[0]);
      var imp=+p[1], clk=+p[2], spd=+p[3], cvn=+p[4], cvv=+p[5];
      if(!d) throw '第'+(i+1)+'行日期无法识别：'+p[0];
      if(isNaN(imp)||isNaN(clk)||isNaN(spd)||isNaN(cvn)||isNaN(cvv)) throw '第'+(i+1)+'行存在无法识别的数值';
      out.push({d:d,imp:imp,clk:clk,spd:spd,cvn:cvn,cvv:cvv});
    }
    if(!out.length) throw '没有解析到任何数据行';
    out.sort(function(a,b){ return a.d<b.d?-1:1; });
    return out;
  }
  function applyRows(rows, badgeText){
    data = rows;
    manualNotify = true;
    renderAll();
    var badge = document.getElementById("dataBadge");
    if (badge && badgeText) badge.textContent = badgeText;
  }
  function renderAll(){
    renderKPIs();
    renderComparison();
    renderSignals();
    renderTrend();
    renderRoas();
    renderTable();
  }

  function bindUi(){
    var seg = document.getElementById("seg");
    if (seg) {
      seg.addEventListener("click", function (ev) {
        var b = ev.target.closest("button");
        if (!b) return;
        filter = b.getAttribute("data-f");
        var btns = this.querySelectorAll("button");
        for (var i = 0; i < btns.length; i++) {
          btns[i].classList.toggle("on", btns[i] === b);
        }
        renderKPIs();
      });
    }
    var csvPanel = document.getElementById("csvPanel");
    var pasteBtn = document.getElementById("pasteBtn");
    if (pasteBtn && csvPanel) {
      pasteBtn.addEventListener("click", function () {
        csvPanel.hidden = !csvPanel.hidden;
        if (!csvPanel.hidden) document.getElementById("csvInput").focus();
      });
    }
    var closeCsv = document.getElementById("closeCsv");
    if (closeCsv && csvPanel) {
      closeCsv.addEventListener("click", function () {
        csvPanel.hidden = true;
        var msg = document.getElementById("csvMsg");
        if (msg) {
          msg.textContent = "";
          msg.className = "csv-msg";
        }
      });
    }
    var applyCsv = document.getElementById("applyCsv");
    if (applyCsv) {
      applyCsv.addEventListener("click", function () {
        var msg = document.getElementById("csvMsg");
        try {
          var rows = parseCsv(document.getElementById("csvInput").value);
          mode = "demo";
          applyRows(rows, "Custom CSV");
          setBadge();
          if (msg) {
            msg.textContent = "Applied " + rows.length + " days";
            msg.className = "csv-msg ok";
          }
        } catch (err) {
          if (msg) {
            msg.textContent = "Parse failed: " + err.message;
            msg.className = "csv-msg err";
          }
        }
      });
    }
    window.addEventListener("resize", function () {
      Object.keys(charts).forEach(function (k) {
        if (charts[k]) charts[k].resize();
      });
    });
  }

  async function boot() {
    bindUi();
    var params = new URLSearchParams(location.search);
    if (params.get("error")) {
      var st = $("statusLine");
      if (st) {
        st.hidden = false;
        st.textContent = "Google connect failed: " + params.get("error");
      }
    }
    await loadStatus();
    await loadReport({ live: false });
    var loadLive = $("loadLiveBtn");
    if (loadLive) {
      loadLive.addEventListener("click", async function () {
        var sel = $("customerSelect");
        var id = sel && sel.value;
        if (!id) return;
        try {
          await loadReport({ live: true, customerId: id });
        } catch (e) {
          var st2 = $("statusLine");
          if (st2) {
            st2.hidden = false;
            st2.textContent = e.message || "Load failed";
          }
        }
      });
    }
    var disc = $("disconnectBtn");
    if (disc) {
      disc.addEventListener("click", async function () {
        await fetch("/api/public/google-ads/logout", {
          method: "POST",
          credentials: "include",
        });
        location.href = "/tools/google-ads-monitor";
      });
    }
    var demoBtn = $("demoBtn");
    if (demoBtn) {
      demoBtn.addEventListener("click", function () {
        loadReport({ live: false });
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
