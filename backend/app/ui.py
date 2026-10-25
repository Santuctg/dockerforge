HTML='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>DockerForge R1 v0.9.0</title><style>
:root{color-scheme:dark;--bg:#0b1220;--surface:#152238;--surface2:#1c2e48;--line:#304562;--text:#e9f0ff;--muted:#a7bbd5;--accent:#669bfa}
*{box-sizing:border-box}body{font:14px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(circle at 80% 0,#18304f 0,transparent 43%),var(--bg);color:var(--text);max-width:1160px;margin:0 auto;padding:34px 22px 70px}h1{font-size:clamp(24px,3vw,34px);margin:0}h1 small{font-size:.52em;color:var(--muted)}h2{margin-top:0}h3{margin-top:26px}p{color:var(--muted)}section{background:var(--surface);border:1px solid var(--line);padding:24px;border-radius:16px;margin:14px 0;box-shadow:0 10px 30px #0002}button,input,select,textarea{font:inherit;border-radius:8px}input,select,textarea{padding:10px;margin:4px;background:var(--surface2);color:var(--text);border:1px solid var(--line);min-width:0}button{padding:9px 13px;margin:4px;color:#fff;background:#315c9e;border:1px solid #416aa9;cursor:pointer;transition:background .15s}button:hover{background:#4578c8}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid #9ebffd;outline-offset:2px}button:disabled{opacity:.5;cursor:default}label{display:inline-flex;align-items:center;gap:5px;color:var(--muted)}label input[type=checkbox]{margin:4px;accent-color:var(--accent)}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:480px;overflow:auto;background:#101b2c;padding:18px;border:1px solid var(--line);border-radius:10px}a{color:#9abfff}#panel>button{margin:4px}#monitorPanel{margin-top:20px}#monitorSummary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:16px 0}#monitorSummary .metric-card{background:var(--surface2);border:1px solid var(--line);border-radius:12px;padding:13px}#monitorSummary .metric-card b{display:block;font-size:24px;font-variant-numeric:tabular-nums}#monitorSummary .metric-card span{color:var(--muted);font-size:12px}#monitorRows{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,330px),1fr));gap:12px;margin:14px 0}#monitorRows .container-card{border:1px solid var(--line);background:var(--surface2);border-radius:12px;padding:15px;min-width:0}#monitorRows .container-card>div{overflow-wrap:anywhere;color:var(--muted)}#monitorRows .container-card strong{font-size:15px}.status-dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#61d6a0;margin-right:7px}.status-dot.off{background:#97a8bc}#collectorHealth{margin:14px 0;padding:12px;background:#10243a;border-left:3px solid #61d6a0;border-radius:6px;color:var(--muted)}#historyPanel{margin-top:22px}#historyPanel .chart-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,390px),1fr));gap:12px}#historyPanel .chart-panel{padding:12px;background:var(--surface2);border:1px solid var(--line);border-radius:12px;min-width:0}#historyPanel canvas{display:block;width:100%;height:auto;touch-action:pan-y}#monitorPanel[hidden],#containerPanel[hidden],#panel[hidden]{display:none!important}@media(max-width:620px){body{padding:16px 10px}section{padding:14px}#monitorSummary{grid-template-columns:repeat(2,minmax(0,1fr))}button{padding:9px}#panel>button{font-size:12px}#portRows input{max-width:135px}}

/* v0.9.0 full workspace design. Kept separate from service behavior. */
:root{--bg:#080f1c;--surface:#111e31;--surface2:#18283e;--line:#293b53;--text:#f0f5ff;--muted:#99abc4;--accent:#4385ef;--good:#42c79b}
html{min-height:100%;background:var(--bg)}body{max-width:none;margin:0;padding:0;min-height:100vh;background:radial-gradient(ellipse at 98% 0,#163353 0,transparent 35%),var(--bg);font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif;font-size:14px}body>h1,body>p{display:none}
#auth{max-width:440px;margin:12vh auto;padding:30px}#auth:empty{display:none}#auth:not(:empty):has(+ #panel:not([hidden])){display:none}#auth input{width:100%;display:block;margin:10px 0}#auth button{width:100%}
#panel{display:grid;grid-template-columns:248px minmax(0,1fr);min-height:100vh;max-width:none;margin:0;padding:0;background:none;border:0;box-shadow:none;border-radius:0}#panel[hidden]{display:none}
.app-sidebar{position:sticky;top:0;align-self:start;height:100vh;background:#0d192a;border-right:1px solid var(--line);padding:26px 14px;display:flex;flex-direction:column;gap:20px}.brand{display:flex;align-items:center;gap:12px;padding:4px 8px 20px;border-bottom:1px solid var(--line)}.brand-mark{display:grid;place-items:center;height:40px;width:40px;background:linear-gradient(150deg,#59a1ff,#3164d1);border-radius:12px;font-weight:800;color:white}.brand strong{display:block;font-size:18px;letter-spacing:-.5px}.brand small{display:block;font-size:9px;letter-spacing:2px;color:var(--muted)}.side-label{font-size:10px;font-weight:800;letter-spacing:1.6px;color:#738ba9;margin:4px 10px 0}.nav-links{display:flex;flex-direction:column;gap:4px}.nav-links .side-label{margin:22px 10px 8px}.nav-links button{display:flex;align-items:center;text-align:left;gap:12px;width:100%;border:1px solid transparent;background:transparent;color:#a4b9d3;font-size:13px;font-weight:600;padding:11px 12px;margin:0;border-radius:9px}.nav-links button:hover{background:#1b304d;color:#fff}.nav-links button.active{background:linear-gradient(95deg,#204c88,#1c3a65);color:#fff;border-color:#345e94}.nav-symbol{width:22px;text-align:center;font-size:18px;line-height:1}.sidebar-foot{margin-top:auto;padding:16px 10px;border-top:1px solid var(--line);font-size:12px;color:#a6b8ce}.sidebar-foot small{display:block;margin:6px 0 0 18px;color:#7890ac}.live-dot{background:var(--good);height:8px;width:8px;display:inline-block;border-radius:50%;margin-right:8px;box-shadow:0 0 14px #42c79b66}
.app-main{min-width:0;max-width:1500px;width:100%;margin:0 auto}.workspace-header{padding:34px clamp(20px,3.2vw,54px) 26px;display:flex;justify-content:space-between;align-items:center;gap:20px;border-bottom:1px solid var(--line)}.eyebrow{font-size:11px;font-weight:800;letter-spacing:1.8px;color:#7899c3}.workspace-header h2{font-size:29px;letter-spacing:-1px;margin:8px 0 0}.workspace-header p{margin:4px 0 0;font-size:13px}.header-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.secure-chip{white-space:nowrap;border:1px solid #265b51;background:#13382f;border-radius:100px;color:#66d4b1;padding:7px 13px;font-size:11px;font-weight:700}.workspace-content{padding:26px clamp(20px,3.2vw,54px) 60px;min-width:0}.workspace-content>div:not([hidden]){margin-top:0}.workspace-content h3{font-size:18px;letter-spacing:-.35px;margin:8px 0 18px}.workspace-content h4{font-size:15px}.workspace-content button{font-size:12px;font-weight:700;background:#254f86;border-color:#35629c;border-radius:8px}.workspace-content button:hover{background:#3371bf}.workspace-content button:disabled{opacity:.45}.workspace-content input,.workspace-content select,.workspace-content textarea{background:#102035;border:1px solid #344963;border-radius:8px;min-height:39px}.workspace-content textarea{line-height:1.55}.workspace-content input:focus,.workspace-content select:focus,.workspace-content textarea:focus{border-color:#75aaff;outline:2px solid #3674cc55}.workspace-content pre{background:#0b1728;border:1px solid #263b56;color:#cbd9ef;font-size:12px;line-height:1.6;max-height:550px}.workspace-content label{margin:8px 4px 8px 0}.workspace-content #monitorSummary{gap:16px}.workspace-content #monitorSummary .metric-card{padding:23px;background:linear-gradient(145deg,#1b304d,#16283e);border-color:#2a4160;border-radius:15px}.workspace-content #monitorSummary .metric-card b{font-size:34px;line-height:1.2}.workspace-content #monitorSummary .metric-card span{font-size:12px}.workspace-content #monitorRows{grid-template-columns:repeat(auto-fit,minmax(min(100%,290px),1fr));gap:14px}.workspace-content #monitorRows .container-card{padding:20px;border-color:#29435e;min-height:154px}.workspace-content #monitorRows .container-card>div{font-size:12px;line-height:1.8;margin:7px 0}.workspace-content #collectorHealth{border-left:3px solid #43cba8;background:#10243a;border-radius:8px;padding:15px;font-size:12px}
.workspace-content #containerRows>div,.workspace-content #resourcePanel>div,.workspace-content #stackPanel>div{background:#16263b;border:1px solid var(--line)!important;padding:17px!important;border-radius:10px;margin:10px 0;line-height:2}.workspace-content #containerRows button,.workspace-content #resourcePanel button,.workspace-content #stackPanel button{margin:5px}.workspace-content #containerPanel>h3:nth-of-type(2){margin-top:35px;padding-top:24px;border-top:1px solid var(--line)}#portRows .portRow{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.portRow input{max-width:155px}#resourcePanel,#stackPanel,#containerPanel,#monitorPanel{background:transparent}#resourcePanel>input,#stackPanel>input{min-width:260px}.workspace-content #historyPanel .chart-panel{background:#182b44;border-color:#2d4665;padding:18px}.workspace-content #historyPanel canvas{margin-top:12px}.advanced-details{border:1px solid #293d58;border-radius:12px;padding:16px 18px;margin-top:28px;background:#101c2c}.advanced-details summary{cursor:pointer;color:#a9bfdd;font-weight:650}.advanced-details pre{margin-top:16px}.workspace-content #consolePanel:not(:empty),.workspace-content #logsPanel:not(:empty){border:1px solid var(--line);border-radius:14px;margin-top:22px;padding:20px;background:#14243a}.workspace-content #resourcePanel:not(:empty),.workspace-content #stackPanel:not(:empty){min-width:0}#resourcePanel>h3:first-child,#stackPanel>h3:first-child{margin-top:0}
@media(max-width:980px){#panel{grid-template-columns:76px minmax(0,1fr)}.app-sidebar{padding:18px 9px}.brand{justify-content:center}.brand strong,.brand small,.side-label,.sidebar-foot,.nav-links button{font-size:0}.nav-links button{justify-content:center;padding:12px 0}.nav-symbol{font-size:21px}.brand-mark{flex-shrink:0}.workspace-header{padding:24px}.workspace-content{padding:20px}}
@media(max-width:640px){#panel{display:block}.app-sidebar{position:relative;height:auto;display:block;padding:13px}.brand{justify-content:start;padding-bottom:10px}.brand strong{font-size:17px}.brand small{font-size:8px}.nav-links{display:flex;flex-direction:row;overflow:auto;gap:7px;margin-top:12px;padding-bottom:6px}.nav-links button{font-size:12px;padding:10px 12px;white-space:nowrap;width:auto}.nav-symbol{font-size:14px;width:auto}.nav-links .side-label,.side-label,.sidebar-foot{display:none}.workspace-header{padding:24px 16px;display:block}.workspace-header h2{font-size:24px}.header-actions{margin-top:16px}.workspace-content{padding:16px}.workspace-content #monitorSummary{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.workspace-content #monitorSummary .metric-card{padding:15px}.workspace-content #monitorRows{grid-template-columns:1fr}#portRows .portRow{gap:3px}.portRow input{max-width:130px}}

/* v0.9.0 workload UX */
.section-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.section-heading h3{margin-bottom:2px}.section-heading p{margin:0 0 16px;font-size:12px}.minor{font-size:12px;font-weight:400;color:var(--muted)}
.filter-bar{display:flex;align-items:center;flex-wrap:wrap;gap:9px;padding:13px;background:#121f32;border:1px solid var(--line);border-radius:13px;margin-bottom:14px}.filter-bar input{flex:1;min-width:210px}.filter-bar select{min-width:145px}.filter-bar span{font-size:12px;color:var(--muted)}
.container-list{display:grid;gap:10px}.workspace-content #containerRows .workload-row{display:flex;align-items:center;justify-content:space-between;gap:18px;background:#16263b;border:1px solid var(--line);border-radius:13px;padding:18px;margin:0;min-width:0;line-height:1.5}.workload-row[hidden]{display:none!important}.workload-meta{min-width:0;flex:1}.workload-meta strong{display:inline-block;font-size:14px;max-width:100%;overflow-wrap:anywhere}.workload-detail,.workload-ports{font-size:12px;color:var(--muted);overflow-wrap:anywhere;margin-top:5px}.workload-ports{color:#a9d0fc}.state-pill{display:inline-block;border-radius:99px;padding:3px 9px;font-size:11px;font-weight:700;margin-left:10px;background:#253448;color:#bbc9dc}.state-running{color:#75eac3;background:#164238}.state-paused{color:#ffdb90;background:#514023}.workload-actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.workspace-content #containerRows .workload-actions button{margin:0}.workspace-content button.primary-action{background:#266cac;border-color:#438acc}.workspace-content button.action-stop{background:#51432a;border-color:#66563a}.workspace-content button.danger-action{background:#51283a;border-color:#81415b}.action-menu{position:relative}.action-menu>summary{list-style:none;cursor:pointer;background:#203c60;border:1px solid #376296;color:#dfecff;border-radius:8px;font-size:12px;padding:9px 12px;font-weight:650}.action-menu>summary::-webkit-details-marker{display:none}.action-menu[open] .action-menu-content{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;padding:10px;margin-top:6px;background:#102138;border:1px solid var(--line);border-radius:10px;min-width:230px;box-shadow:0 12px 30px #0004}.action-menu-content button{white-space:nowrap}.create-panel{margin-top:26px;padding:20px;background:#121f33;border:1px solid var(--line);border-radius:14px}.create-panel>summary,.advanced-options>summary{cursor:pointer;font-weight:750;font-size:16px}.create-panel[open]>summary{padding-bottom:18px;border-bottom:1px solid var(--line)}.form-section{padding:12px 0;border-bottom:1px solid #273b55}.form-section h4{margin:8px 0}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.field{display:flex;flex-direction:column;align-items:stretch!important;font-size:12px;font-weight:650}.field input{width:100%}.port-labels{display:grid;grid-template-columns:1.4fr 1fr 1fr .8fr 78px;gap:7px;color:var(--muted);font-size:11px;padding-left:4px}.portRow{display:grid!important;grid-template-columns:1.4fr 1fr 1fr .8fr 78px;gap:7px!important;align-items:center}.portRow input{max-width:none!important;width:100%}.portRow select{width:100%}.portRow button{margin:0!important}.check-row{display:flex!important;margin:12px 0!important;font-size:12px}.advanced-options{padding:17px 0;border-bottom:1px solid var(--line)}.advanced-options>summary{font-size:14px}.form-footer{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding-top:17px}.form-footer p{width:100%;margin:4px;color:#a9d0fc}
@media(max-width:1000px){.workspace-content #containerRows .workload-row{align-items:stretch;flex-direction:column}.workload-actions{justify-content:flex-start}}@media(max-width:680px){.form-grid{grid-template-columns:1fr}.port-labels{display:none}.portRow{grid-template-columns:repeat(2,minmax(0,1fr));padding:10px;border:1px solid var(--line);border-radius:9px;margin:7px 0}.portRow button{grid-column:span 2}.filter-bar input{min-width:100%}}
.detail-panel{margin:18px 0;padding:20px;background:#14273f;border:1px solid #3a5f85;border-radius:14px}.detail-header{display:flex;align-items:center;justify-content:space-between;gap:12px}.detail-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.detail-content{min-width:0}.detail-group{background:#102138;border:1px solid #2a4464;border-radius:10px;padding:14px;margin:10px 0}.detail-group h4{margin:0 0 12px}.detail-fact{display:flex;justify-content:space-between;gap:20px;padding:9px 0;border-top:1px solid #273a54;overflow-wrap:anywhere}.detail-fact span{color:#9bb7d3;min-width:120px}.detail-fact strong{max-width:72%;text-align:right;overflow-wrap:anywhere}.detail-content input{max-width:420px;margin:10px}.details-json{max-height:460px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere}.full-width-textarea{width:100%;min-height:85px;box-sizing:border-box;background:#0e2034;border:1px solid #34506f;border-radius:9px;color:#e4f0ff;padding:12px}.hint{font-size:12px;color:#b5c8dd}.create-panel select{width:100%;min-height:38px;background:#0e2034;color:#e4f0ff;border:1px solid #34506f;border-radius:8px}
.detail-fact .copy-field{font-size:11px;padding:5px 10px;flex-shrink:0;margin:0 0 0 8px}.detail-fact strong{min-width:0;flex:1}.log-workspace,.console-workspace{min-height:320px;max-height:65vh;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;line-height:1.65;background:#081523;padding:18px;border:1px solid #294769;border-radius:10px}.console-controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.console-controls input{flex:1;max-width:none;min-width:180px;margin:0}.console-controls button{flex-shrink:0}.tool-strip{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0}.tool-strip input[type=search]{flex:1;min-width:180px;max-width:360px}.tool-strip label{font-size:12px;color:#b5c8dd}.tool-status{font-size:12px;color:#aac3df}.log-workspace{white-space:pre-wrap;overflow-wrap:anywhere}.console-workspace{white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:650px){.detail-fact{flex-wrap:wrap}.detail-fact strong{text-align:left;max-width:100%;flex-basis:70%}}

/* DockerForge v0.9.0: focused details workspace */
#containerDetailPanel.fullscreen-details{position:fixed!important;inset:12px!important;z-index:1000!important;background:#10243b!important;overflow:auto!important;margin:0!important;max-width:none!important;box-shadow:0 0 0 200vmax #000b;padding:20px!important}
#containerDetailPanel.fullscreen-details .detail-content{min-height:calc(100vh - 200px)}
#containerDetailPanel.fullscreen-details .log-workspace,#containerDetailPanel.fullscreen-details .console-workspace{max-height:calc(100vh - 260px);min-height:calc(100vh - 260px)}
.log-workspace{overflow:auto;white-space:pre-wrap}.log-workspace .log-line{white-space:pre-wrap}
@media(max-width:650px){#containerDetailPanel.fullscreen-details{inset:4px!important;padding:10px!important}.tool-strip{align-items:flex-start}}

.host-resource-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:15px 0 25px}.host-stat{padding:16px;border:1px solid #324d6d;background:#162942;border-radius:10px}.host-stat span{display:block;color:#a8bdd5;font-size:12px}.host-stat strong{display:block;font-size:19px;margin-top:7px}.compose-editor{display:grid;gap:12px;padding:18px;border:1px solid #304968;border-radius:12px;background:#14253b}.compose-editor textarea{width:100%;background:#0d2036;color:#fff;font:13px monospace;resize:vertical}.compose-stack-row{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:14px;border-bottom:1px solid #334a67}.compose-stack-row strong{margin-right:auto}
</style></head><body><h1>DockerForge <small>R1 v0.9.0</small></h1><p>Single-host Docker management preview. Single-host preview: Compose stacks, bounded logs and command console (non-interactive).</p><section id="auth"></section><section id="panel" hidden>
 <aside class="app-sidebar" aria-label="Main navigation">
 <div class="brand"><span class="brand-mark">DF</span><span><strong>DockerForge</strong><small>HOST CONTROL · R1</small></span></div>
 <div class="side-label">WORKSPACE</div>
 <nav class="nav-links">
 <button data-action="navigate" data-view="dashboard"><span class="nav-symbol">◫</span>Overview</button>
 <button data-action="navigate" data-view="containers"><span class="nav-symbol">▣</span>Containers</button>
 <button data-action="navigate" data-view="images"><span class="nav-symbol">◈</span>Images</button>
 <button data-action="navigate" data-view="networks"><span class="nav-symbol">⌁</span>Networks</button>
 <button data-action="navigate" data-view="volumes"><span class="nav-symbol">▤</span>Volumes</button>
 <button data-action="navigate" data-view="compose"><span class="nav-symbol">⬡</span>Compose stacks</button>
 <div class="side-label">OBSERVABILITY</div>
 <button data-action="navigate" data-view="alerts"><span class="nav-symbol">♧</span>Alert rules</button>
 <button data-action="navigate" data-view="diagnostics"><span class="nav-symbol">⊕</span>Diagnostics</button>
 <button data-action="navigate" data-view="users"><span class="nav-symbol">♙</span>User management</button>
 <button data-action="navigate" data-view="backups"><span class="nav-symbol">▥</span>Backup center</button>
 <button data-action="navigate" data-view="audit"><span class="nav-symbol">☷</span>Audit trail</button>
 <button data-action="navigate" data-view="raw"><span class="nav-symbol">{ }</span>Raw containers</button>
 </nav><div class="sidebar-foot"><span class="live-dot"></span>Connected to local Docker host <small>R1 · v0.9.0</small></div>
 </aside>
 <main class="app-main">
 <header class="workspace-header"><div><div class="eyebrow">HOST MANAGEMENT / <span id="breadcrumb">OVERVIEW</span></div><h2 id="pageTitle">Overview</h2><p id="pageDescription">Container health, resources, and host activity at a glance.</p></div><div class="header-actions"><span class="secure-chip">● HTTPS</span><button class="outline" type="button" data-action="refresh-view">↻ Refresh</button><button class="outline" type="button" data-action="logout">Sign out</button></div></header>
 <div class="workspace-content">
<div id="monitorPanel" hidden><h3>Host resources</h3><div id="hostMetrics" class="host-resource-grid" aria-live="polite">Loading host metrics…</div><h3>Container monitoring</h3><p>CPU / RAM / network rates · background samples every 5s when collector is active</p><div id="monitorSummary"></div><div id="monitorRows"></div><button data-action="refresh-monitor">Refresh metrics</button><label><input type="checkbox" id="metricsRefresh" data-action="toggle-metrics"> Auto-refresh dashboard & metrics (5s)</label><label><input type="checkbox" id="fastDisplay" data-action="toggle-metrics"> Fast display refresh (1s; underlying samples ~5s)</label><div id="collectorHealth" aria-live="polite"></div><p style="font-size:12px;color:#9cafd0">History is collected by the background systemd metrics service even when the dashboard is closed.</p><div id="historyPanel"></div></div><div id="containerPanel" hidden>
<div class="section-heading"><div><h3>Containers</h3><p>Find workloads, inspect ports and control lifecycle.</p></div><button type="button" data-action="list-containers">Refresh list</button></div>
<div class="filter-bar"><input id="containerSearch" placeholder="Search name, image, ID or port" aria-label="Search containers" data-action="filter-containers"><select id="containerStateFilter" aria-label="Filter by state" data-action="filter-containers"><option value="all">All states</option><option value="running">Running</option><option value="exited">Exited</option><option value="created">Created</option><option value="paused">Paused</option></select><span id="containerMatchCount" aria-live="polite"></span></div>
<div id="containerRows" class="container-list"></div><section id="containerDetailPanel" class="detail-panel" hidden aria-live="polite"></section>
<details class="create-panel" id="createContainerDetails"><summary>Create container <span class="minor">Admin · image, published ports and security</span></summary>
<div class="form-section"><h4>1. Basic settings</h4><div class="form-grid"><label class="field">Container name<input id="newName" placeholder="e.g. my-web"></label><label class="field">Image reference<input id="newImage" placeholder="e.g. nginx:alpine"></label></div></div>
<div class="form-section"><h4>2. Published ports <span class="minor">Optional; defaults to localhost</span></h4><div class="port-labels"><span>Host IP</span><span>Host port</span><span>Container port</span><span>Protocol</span></div><div id="portRows"><div class="portRow"><input class="hostIP" aria-label="Host IP" placeholder="127.0.0.1" value="127.0.0.1"><input class="hostPort" aria-label="Host port" type="number" min="1" max="65535" placeholder="8091"><input class="containerPort" aria-label="Container port" type="number" min="1" max="65535" placeholder="80"><select class="portProtocol" aria-label="Protocol"><option value="tcp">TCP</option><option value="udp">UDP</option></select><button type="button" data-action="remove-port">Remove</button></div></div><button type="button" data-action="add-port">+ Add port mapping</button><label class="check-row"><input type="checkbox" id="publicPorts">I acknowledge that non-localhost host IPs expose ports to networks</label></div>
<div class="form-section"><h4>3. Runtime settings</h4><div class="form-grid"><label class="field">Restart policy<select id="newRestart"><option value="unless-stopped">Unless stopped</option><option value="always">Always</option><option value="on-failure">On failure</option><option value="no">No</option></select></label><label class="field">Memory limit (MiB, optional)<input id="newMemory" type="number" min="16" max="1048576" placeholder="e.g. 512"></label></div></div>
<div class="form-section"><h4>4. Environment variables <span class="minor">Optional · one KEY=value per line</span></h4><textarea id="newEnvironment" class="full-width-textarea" rows="4" placeholder="APP_ENV=production"></textarea><p class="hint">Avoid entering passwords or tokens here when possible: Docker environment variables may be visible via inspect.</p></div>
<details class="advanced-options"><summary>5. Bind mounts (host access · high risk)</summary><textarea id="newMounts" class="full-width-textarea" rows="3" placeholder="/host/path:/container/path:ro"></textarea><p class="hint">One absolute source:target[:ro|rw] mount per line. Bind mounts grant access to host files. Explicit host-risk acknowledgement required.</p></details>
<details class="advanced-options"><summary>6. Advanced security options</summary><label class="check-row"><input type="checkbox" id="highRisk">Privileged container (high risk)</label><label class="check-row"><input type="checkbox" id="ackRisk">I understand the host-level risks</label></details>
<div class="form-footer"><button data-action="create-container" data-start="0">Create only</button><button class="primary-action" data-action="create-container" data-start="1">Create &amp; Start</button><p id="containerMsg" aria-live="polite"></p></div></details></div><div id="resourcePanel"></div><div id="stackPanel"></div><div id="consolePanel"></div><div id="logsPanel"></div><details id="diagnosticsDetail" class="advanced-details"><summary>Advanced diagnostics · JSON response</summary><pre id="data"></pre></details></div></main></section><script nonce="__CSP_NONCE__">
const api='/api/v1/';let csrf='';let currentRole='viewer';async function call(path,method='GET',body=null,setup=false){const headers={'Content-Type':'application/json'};if(method!=='GET')headers['X-CSRF-Token']=csrf;if(setup)headers['X-Setup-Token']=document.querySelector('#bootstrap').value;const r=await fetch(api+path,{method,credentials:'same-origin',headers,body:body?JSON.stringify(body):null});const j=await r.json();if(!r.ok)throw Error(j.error?.message||JSON.stringify(j.detail)||'Request failed');return j}
async function alertRulesPage(){
 const pane=document.querySelector('#resourcePanel');pane.replaceChildren();
 const title=document.createElement('h3');title.textContent='Alert management';pane.appendChild(title);
 try{
 const [rules,state,containers,notification]=await Promise.all([call('monitoring/alert-rules'),call('monitoring/alerts'),call('docker/containers'),call('monitoring/notifications/config')]);
 const items=containers.items||[];
 const getName=(ident)=>{const c=items.find(v=>v.Id===ident||v.Id.startsWith(ident));return c?((c.Names||[])[0]||c.Id).replace(/^[/]/,''):ident.slice(0,12)};
 const section=(label)=>{const h=document.createElement('h4');h.textContent=label;pane.appendChild(h)};
 section('Active alerts');
 const active=Object.entries(state.active||{});
 if(!active.length){const p=document.createElement('p');p.textContent='No active alerts';pane.appendChild(p)}
 for(const [key,entry] of active){const row=document.createElement('div');row.style.cssText='padding:9px;border-bottom:1px solid #304562';const status=entry.acknowledged_at?'Acknowledged':'Firing';const text=document.createElement('span');text.textContent=getName(entry.container_id)+' · '+entry.type+' · '+status+' · delivery: '+(entry.delivery||'unknown')+' ';row.appendChild(text);
 if(!entry.acknowledged_at&&canOperate()){const btn=document.createElement('button');btn.textContent='Acknowledge';btn.onclick=async()=>{try{await call('monitoring/alerts/ack','POST',{key});await alertRulesPage()}catch(e){alert(e.message)}};row.appendChild(btn)}pane.appendChild(row)}
 section('Rule editor');
 if(canAdmin()){
 const select=document.createElement('select');select.setAttribute('aria-label','Select container');
 const blank=document.createElement('option');blank.value='';blank.textContent='Select a container';select.appendChild(blank);
 for(const item of items){const opt=document.createElement('option');opt.value=item.Id;opt.textContent=getName(item.Id)+' ('+item.Id.slice(0,12)+')';select.appendChild(opt)}
 const cpu=document.createElement('input');cpu.type='number';cpu.value=90;cpu.min=0.1;cpu.max=10000;cpu.step='any';cpu.title='CPU % threshold';cpu.style.width='90px';
 const mem=document.createElement('input');mem.type='number';mem.value=90;mem.min=0.1;mem.max=100;mem.step='any';mem.title='RAM % threshold';mem.style.width='90px';
 const stop=document.createElement('input');stop.type='checkbox';
 const enabled=document.createElement('input');enabled.type='checkbox';enabled.checked=true;
 const pick=()=>{const existing=rules.items.find(r=>r.container_id===select.value);cpu.value=existing?existing.cpu_threshold:90;mem.value=existing?existing.memory_threshold:90;stop.checked=Boolean(existing?.alert_on_stopped);enabled.checked=existing?existing.enabled:true};select.onchange=pick;
 const save=document.createElement('button');save.textContent='Save / update rule';save.onclick=async()=>{try{if(!select.value)throw Error('Select a container first');await call('monitoring/alert-rules/'+encodeURIComponent(select.value),'PUT',{cpu_threshold:Number(cpu.value),memory_threshold:Number(mem.value),alert_on_stopped:stop.checked,enabled:enabled.checked});await alertRulesPage()}catch(e){alert(e.message)}};
 const sl=document.createElement('label');sl.append(stop,document.createTextNode(' Alert when stopped '));const el=document.createElement('label');el.append(enabled,document.createTextNode(' Enabled '));
 pane.append(select,document.createTextNode(' CPU % '),cpu,document.createTextNode(' RAM % '),mem,sl,el,save);
 }
 section('Saved rules');
 for(const rule of rules.items){const row=document.createElement('div');row.style.cssText='padding:8px;border-bottom:1px solid #304562';const text=document.createElement('span');text.textContent=getName(rule.container_id)+' · CPU '+rule.cpu_threshold+'% · RAM '+rule.memory_threshold+'% · stopped '+(rule.alert_on_stopped?'yes':'no')+' · '+(rule.enabled?'enabled':'disabled')+' ';row.appendChild(text);
 if(canAdmin()){const del=document.createElement('button');del.textContent='Delete rule';del.onclick=async()=>{if(!confirm('Delete alert rule for '+getName(rule.container_id)+'?'))return;try{await call('monitoring/alert-rules/'+encodeURIComponent(rule.container_id),'DELETE');await alertRulesPage()}catch(e){alert(e.message)}};row.appendChild(del)}pane.appendChild(row)}
 section('Alert event history (last 50)');
 const history=document.createElement('div');for(const ev of (state.events||[]).slice(-50).reverse()){const line=document.createElement('div');const time=new Date(ev.ts*1000).toLocaleString();line.textContent=time+' · '+ev.event+' · '+getName(ev.key.split(':')[0])+' · '+ev.type+(ev.actor?' · '+ev.actor:'');history.appendChild(line)}pane.appendChild(history);
 section('Email notifications');const info=document.createElement('p');info.textContent='SMTP: '+(notification.enabled?'enabled':'disabled')+' · '+(notification.configured?'configured':'not configured')+' · credentials stored only in server environment · delivery has no retry queue';pane.appendChild(info);
 if(canAdmin()){const test=document.createElement('button');test.textContent='Send test email';test.disabled=!notification.enabled||!notification.configured;test.onclick=async()=>{if(!confirm('Send a test notification to the configured recipient?'))return;try{const response=await call('monitoring/notifications/test','POST',{});alert('Delivery: '+response.delivery)}catch(e){alert(e.message)}};pane.appendChild(test)}
 }catch(err){const pre=document.createElement('pre');pre.textContent=err.message;pane.appendChild(pre)}
}

async function init(){const c=await call('auth/csrf');csrf=c.csrf_token;const s=await call('auth/setup/status');try{const u=await call('auth/session');show(u);return}catch(e){};document.querySelector('#auth').innerHTML=s.setup_required?'<h2>First-run Super Admin setup</h2><input id="bootstrap" placeholder="Bootstrap token from installer"><input id="username" placeholder="Username"><input id="password" type="password" placeholder="Password (12+ chars)"><button data-action="setup">Create Super Admin</button><p id="msg"></p>':'<h2>Login</h2><input id="username" placeholder="Username"><input id="password" type="password" placeholder="Password"><button data-action="login">Sign in</button><p id="msg"></p>'}
function values(){return {username:document.querySelector('#username').value,password:document.querySelector('#password').value}}
async function setup(){try{await call('auth/setup','POST',values(),true);await init()}catch(e){document.querySelector('#msg').textContent=e.message}}
async function login(){try{const a=await call('auth/login','POST',values());csrf=a.csrf_token;show(a)}catch(e){document.querySelector('#msg').textContent=e.message}}
function show(user){currentRole=user.role;document.querySelector('#auth').textContent='Signed in as '+user.username+' ('+user.role+')';document.querySelector('#panel').hidden=false;dashboardPage()}
async function loadData(path){try{document.querySelector('#data').textContent=JSON.stringify(await call(path),null,2)}catch(e){document.querySelector('#data').textContent=e.message}}
function canOperate(){return ['super_admin','admin','operator'].includes(currentRole)}
function canAdmin(){return ['super_admin','admin'].includes(currentRole)}
function safeText(value){return String(value??'')}
function filterContainerRows(){
 const q=(document.querySelector('#containerSearch')?.value||'').trim().toLowerCase();
 const state=document.querySelector('#containerStateFilter')?.value||'all';let shown=0;
 for(const row of document.querySelectorAll('#containerRows .workload-row')){
  const match=(!q||row.dataset.search.includes(q))&&(state==='all'||row.dataset.state===state);
  row.hidden=!match;if(match)shown++;
 }
 const count=document.querySelector('#containerMatchCount');if(count)count.textContent=shown+' matching containers';
}
function removePortRow(button){const rows=document.querySelectorAll('#portRows .portRow');if(rows.length>1){button.closest('.portRow').remove()}else{for(const el of rows[0].querySelectorAll('input'))el.value=el.classList.contains('hostIP')?'127.0.0.1':''}}
async function listContainers(){
 document.querySelector('#containerPanel').hidden=false;
 const area=document.querySelector('#containerRows');area.replaceChildren();
 try{const data=await call('docker/containers');window.lastContainerList=data.items||[];
 for(const item of data.items||[]){
  const name=((item.Names||[''])[0]||item.Id).replace(/^[/]/,'');const id=item.Id;
  const state=String(item.State||'unknown').toLowerCase();const image=String(item.Image||'—');
  const portText=(item.Ports||[]).map(p=>{const dest=p.PrivatePort+((p.Type||'tcp')==='udp'?'/udp':'/tcp');return p.PublicPort?(p.IP||'0.0.0.0')+':'+p.PublicPort+' → '+dest:dest}).join(' · ')||'No published ports';
  const row=document.createElement('article');row.className='workload-row';row.dataset.search=[name,id,image,portText].join(' ').toLowerCase();row.dataset.state=state;
  const meta=document.createElement('div');meta.className='workload-meta';
  const title=document.createElement('strong');title.textContent=name;title.title=name;
  const badge=document.createElement('span');badge.className='state-pill state-'+(state==='running'?'running':state==='paused'?'paused':'inactive');badge.textContent=state;
  const detail=document.createElement('div');detail.className='workload-detail';detail.textContent=image+' · '+id.slice(0,12);
  const ports=document.createElement('div');ports.className='workload-ports';ports.textContent=portText;
  meta.append(title,badge,detail,ports);
  const actions=document.createElement('div');actions.className='workload-actions';
  function action(label,fn,cls=''){const b=document.createElement('button');b.textContent=label;b.type='button';b.className=cls;b.onclick=fn;return b}
  actions.append(action('Inspect',()=>viewContainerDetails(id,name,state)));
  actions.append(action('Logs',()=>viewLogs(id)));
  if(canOperate()){
   if(state==='running')actions.append(action('Stop',()=>operate(id,'stop'),'action-stop'));
   else if(state==='exited'||state==='created')actions.append(action('Start',()=>operate(id,'start'),'primary-action'));
  }
  const menu=document.createElement('details');menu.className='action-menu';const trigger=document.createElement('summary');trigger.textContent='More actions';menu.append(trigger);
  const choices=document.createElement('div');choices.className='action-menu-content';
  choices.append(action('Stats',()=>viewContainerDetails(id,name,state,'stats')));
  if(canOperate()){
   choices.append(action('Command',()=>commandPanel(id)));
   for(const act of ['start','stop','restart','pause','unpause']){
    const enabled=act==='restart'?state==='running':act==='start'?['exited','created'].includes(state):act==='stop'?state==='running':act==='pause'?state==='running':state==='paused';
    if(enabled)choices.append(action(act[0].toUpperCase()+act.slice(1),()=>operate(id,act)));
   }
  }
  if(canAdmin())choices.append(action('Delete container',()=>deleteContainer(id,name),'danger-action'));
  menu.append(choices);actions.append(menu);row.append(meta,actions);area.append(row);
 }
 filterContainerRows();
 }catch(err){area.textContent=err.message}
}
function friendlyTime(value){
 if(!value || String(value).startsWith('0001-'))return 'Not started';
 const date=new Date(value);
 return Number.isNaN(date.getTime())?String(value):date.toLocaleString()+' (local)';
}
function detailsLine(label,value,copyable=false){
 const line=document.createElement('div');line.className='detail-fact';
 const term=document.createElement('span');term.textContent=label;
 const val=document.createElement('strong');val.textContent=value===null||value===undefined||value===''?'—':String(value);
 line.append(term,val);
 if(copyable&&value!==null&&value!==undefined&&String(value)!==''){
  const copy=document.createElement('button');copy.type='button';copy.className='copy-field';copy.textContent='Copy';
  copy.setAttribute('aria-label','Copy '+label);
  copy.onclick=async()=>{try{await navigator.clipboard.writeText(String(value));copy.textContent='Copied';setTimeout(()=>copy.textContent='Copy',1500)}catch(e){copy.textContent='Copy unavailable'}};
  line.append(copy);
 }
 return line;
}
function detailsGroup(title,items){
 const group=document.createElement('section');group.className='detail-group';
 const h=document.createElement('h4');h.textContent=title;group.append(h);
 for(const item of items){const [label,value,copyable]=item;group.append(detailsLine(label,value,!!copyable))}
 return group;
}
function bytesHuman(n){if(!Number.isFinite(Number(n))||Number(n)<0)return '—';if(Number(n)===0)return 'Unlimited / default';return (Number(n)/1048576).toFixed(1)+' MiB'}
function renderInspectDetails(root,data,tab){
 const config=data.Config||{}, host=data.HostConfig||{}, state=data.State||{},net=data.NetworkSettings||{};
 if(tab==='overview'){
  root.append(detailsGroup('Container', [['Name',(data.Name||'').replace(/^[/]/,'')],['ID',data.Id,true],['Image',config.Image||data.Image],['Status',state.Status],['Started at',friendlyTime(state.StartedAt)],['Created',friendlyTime(data.Created)],['Restart policy',host.RestartPolicy?.Name],['Memory limit',bytesHuman(host.Memory)]]));
 }else if(tab==='configuration'){
  root.append(detailsGroup('Runtime',[['Entrypoint',(config.Entrypoint||[]).join(' ')],['Command',(config.Cmd||[]).join(' ')],['Working directory',config.WorkingDir],['User',config.User||'Image default'],['Privileged',host.Privileged?'Yes':'No'],['Restart policy',host.RestartPolicy?.Name],['Memory limit',bytesHuman(host.Memory)]]));
  const note=document.createElement('p');note.className='hint';note.textContent='Environment values may contain secrets. Hidden by default; use Docker CLI under authorized supervision if needed.';root.append(note);
 }else if(tab==='network'){
  const exposed=host.PortBindings||{};const ports=Object.entries(exposed).flatMap(([port,bindings])=>(bindings||[]).map(x=>`${x.HostIp||'0.0.0.0'}:${x.HostPort||'auto'} → ${port}`));
  root.append(detailsGroup('Connectivity',[['Network mode',host.NetworkMode],['Published ports',ports.join(' · ')||'None',ports.length>0],['Container ports',Object.keys(config.ExposedPorts||{}).join(', ')||'None']]));
  for(const [name,item] of Object.entries(net.Networks||{}))root.append(detailsGroup('Network: '+name,[['IP address',item.IPAddress,true],['Subnet prefix',item.IPPrefixLen?'/'+item.IPPrefixLen:'—'],['Gateway',item.Gateway,true],['MAC address',item.MacAddress,true],['DNS aliases',(item.DNSNames||item.Aliases||[]).join(', ')||'None'],['Network ID',item.NetworkID,true]]));
 }else if(tab==='mounts'){
  const mounts=data.Mounts||[];
  if(!mounts.length){root.append(detailsGroup('Mounts',[['Configured mounts','None']]));return}
  for(const [index,m] of mounts.entries())root.append(detailsGroup('Mount '+(index+1),[['Type',m.Type],['Source',m.Source],['Destination',m.Destination],['Access',m.RW?'Read / write':'Read only'],['Name',m.Name]]));
 }else if(tab==='raw'){
  const note=document.createElement('p');note.className='hint';note.textContent='Raw Docker Inspect may expose environment secrets and host paths. Display only when intentionally requested.';
  const disclosure=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Reveal raw inspection JSON';const pre=document.createElement('pre');pre.className='details-json';pre.textContent=JSON.stringify(data,null,2);disclosure.append(summary,pre);root.append(note,disclosure);
 }
}
const consoleHistory=new Map();
function saveTextFile(text,filename){const blob=new Blob([text],{type:'text/plain;charset=utf-8'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=filename;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function safeFilename(value){return String(value).replace(/[^a-zA-Z0-9_.-]/g,'_').slice(0,72)}
function makeToolButton(label,handler){const button=document.createElement('button');button.type='button';button.textContent=label;button.onclick=handler;return button}
function setupLogWorkspace(content,id){
 content.replaceChildren();let currentText='',inFlight=false,timer=null;let follow=true;
 const controls=document.createElement('div');controls.className='tool-strip';
 const search=document.createElement('input');search.type='search';search.placeholder='Filter fetched logs';search.setAttribute('aria-label','Search container logs');
 const tail=document.createElement('select');tail.setAttribute('aria-label','Number of log lines');for(const n of [100,500,1000]){const opt=document.createElement('option');opt.value=String(n);opt.textContent=n+' lines';tail.append(opt)}tail.value='100';
 const timestamps=document.createElement('input');timestamps.type='checkbox';const tsLabel=document.createElement('label');tsLabel.append(timestamps,document.createTextNode(' Timestamps'));
 const filteredDownload=document.createElement('input');filteredDownload.type='checkbox';const downloadLabel=document.createElement('label');downloadLabel.append(filteredDownload,document.createTextNode(' Download filtered'));
 const output=document.createElement('pre');output.className='details-json log-workspace';const scrollCheck=document.createElement('input');scrollCheck.type='checkbox';scrollCheck.checked=true;const scrollLabel=document.createElement('label');scrollLabel.append(scrollCheck,document.createTextNode(' Auto-scroll')); 
 const status=document.createElement('span');status.className='tool-status';status.setAttribute('aria-live','polite');
 const filter=()=>{const q=search.value.toLowerCase();return q?currentText.split('\\n').filter(x=>x.toLowerCase().includes(q)).join('\\n'):currentText};
 const render=()=>{const atBottom=output.scrollHeight-output.scrollTop-output.clientHeight<50;const value=filter();output.textContent=value||'(no matching logs)';if(scrollCheck.checked&&(atBottom||follow))output.scrollTop=output.scrollHeight;status.textContent=(search.value?value.split('\\n').filter(Boolean).length+' matching lines · ':'')+'Last '+tail.value+' lines · '+new Date().toLocaleTimeString()};
 const refresh=async()=>{if(inFlight)return;inFlight=true;try{const url='containers/'+encodeURIComponent(id)+'/logs?tail='+encodeURIComponent(tail.value)+'&timestamps='+String(timestamps.checked);const r=await call(url);if(!content.isConnected)return;currentText=String(r.output||'');render();if(r.truncated)status.textContent+=' · Output truncated to 256 KiB'}catch(e){status.textContent='Log refresh failed: '+e.message}finally{inFlight=false}};
 const checkbox=document.createElement('input');checkbox.type='checkbox';const label=document.createElement('label');label.append(checkbox,document.createTextNode(' Follow (5s polling)'));const pauseButton=makeToolButton('Pause',()=>{follow=!follow;pauseButton.textContent=follow?'Pause':'Resume';status.textContent=follow?'Follow resumed':'Follow paused'});
 const cleanup=()=>{if(timer){clearInterval(timer);timer=null}};
 checkbox.onchange=()=>{cleanup();if(checkbox.checked)timer=setInterval(()=>{if(follow&&!document.hidden&&content.isConnected)refresh();else if(!content.isConnected)cleanup()},5000)};
 search.oninput=render;tail.onchange=refresh;timestamps.onchange=refresh;
 controls.append(search,tail,tsLabel,makeToolButton('Refresh',refresh),makeToolButton('Download',()=>saveTextFile(filteredDownload.checked?filter():currentText,'dockerforge-'+safeFilename(id.slice(0,12))+'-logs.txt')),downloadLabel,label,pauseButton,scrollLabel,status);
 content.append(controls,output);return refresh();
}
function setupConsoleWorkspace(content,id){
 content.replaceChildren();const info=document.createElement('p');info.className='hint';info.textContent='One-shot command only. History stays in this browser tab; do not enter secrets.';
 const controls=document.createElement('div');controls.className='console-controls';const field=document.createElement('input');field.placeholder='e.g. whoami';field.setAttribute('aria-label','Container command');
 const output=document.createElement('pre');output.className='details-json console-workspace';const status=document.createElement('span');status.className='tool-status';status.setAttribute('aria-live','polite');
 const history=consoleHistory.get(id)||[];consoleHistory.set(id,history);let cursor=history.length;
 const historySelect=document.createElement('select');historySelect.setAttribute('aria-label','Previous commands');
 const refreshHistory=()=>{historySelect.replaceChildren();const empty=document.createElement('option');empty.value='';empty.textContent='Previous commands';historySelect.append(empty);for(const cmd of [...history].reverse()){const opt=document.createElement('option');opt.value=cmd;opt.textContent=cmd.slice(0,100);historySelect.append(opt)}};
 historySelect.onchange=()=>{if(historySelect.value)field.value=historySelect.value};refreshHistory();
 field.addEventListener('keydown',event=>{if(event.key==='ArrowUp'&&history.length){event.preventDefault();cursor=Math.max(0,cursor-1);field.value=history[cursor]}else if(event.key==='ArrowDown'){event.preventDefault();cursor=Math.min(history.length,cursor+1);field.value=cursor===history.length?'':history[cursor]}else if(event.key==='Enter'){event.preventDefault();run.click()}});
 const run=makeToolButton('Execute',async()=>{const cmd=field.value.trim();if(!cmd)return;const argv=cmd.split(/\\s+/).filter(Boolean);run.disabled=true;status.textContent='Executing…';try{const result=await call('containers/'+encodeURIComponent(id)+'/exec','POST',{argv});output.textContent=String(result.output||JSON.stringify(result,null,2));status.textContent='Command completed';if(history.at(-1)!==cmd){history.push(cmd);if(history.length>30)history.shift()}cursor=history.length;refreshHistory()}catch(e){output.textContent=e.message;status.textContent='Command failed'}finally{run.disabled=false}});
 controls.append(field,historySelect,run,makeToolButton('Clear output',()=>{output.textContent='';status.textContent='Output cleared'}),makeToolButton('Copy output',async()=>{try{await navigator.clipboard.writeText(output.textContent);status.textContent='Output copied'}catch(e){status.textContent='Clipboard permission unavailable'}}));
 content.append(info,controls,status,output);
}
function editEl(tag,props={},children=[]){const el=document.createElement(tag);Object.assign(el,props);el.append(...children);return el}
function editField(label,input){return editEl('label',{className:'edit-field'},[editEl('span',{textContent:label}),input])}
function formatPortLines(bindings){return (bindings||[]).map(p=>{const ip=p.host_ip===''?'*':(p.host_ip.includes(':')?'['+p.host_ip+']':p.host_ip);return ip+':'+(p.host_port??'')+':'+p.container_port+'/'+p.protocol}).join(String.fromCharCode(10))}
function parsePortLines(text){const out=[];for(const raw of text.split(String.fromCharCode(10))){const line=raw.trim();if(!line)continue;const slash=line.lastIndexOf('/');const proto=slash>0?line.slice(slash+1):'tcp';let spec=slash>0?line.slice(0,slash):line;let host_ip='127.0.0.1';if(spec.startsWith('[')){const close=spec.indexOf(']:');if(close<0)throw Error('Invalid IPv6 port line: '+line);host_ip=spec.slice(1,close);spec=spec.slice(close+2)}const parts=spec.split(':');if(parts.length===3){host_ip=parts.shift()}else if(parts.length!==2||spec!==parts.join(':'))throw Error('Port lines look like 8080:80, 0.0.0.0:443:443/tcp, *::80 (random port) or [::]:443:443');if(host_ip==='*')host_ip='';const host_port=parts[0]===''?null:Number(parts[0]);const container_port=Number(parts[1]);if((host_port!==null&&!Number.isInteger(host_port))||!Number.isInteger(container_port))throw Error('Invalid port line: '+line);out.push({host_ip,host_port,container_port,protocol:proto})}return out}
function formatCommand(cmd){return cmd?JSON.stringify(cmd):''}
function parseCommand(text){const t=text.trim();if(!t)return null;let value;try{value=JSON.parse(t)}catch(e){value=null}if(!Array.isArray(value)||!value.every(x=>typeof x==='string'))throw Error('Command must be a JSON array of strings, e.g. ["nginx","-g","daemon off;"]');return value}
function formatEnv(env){return Object.entries(env||{}).map(([k,v])=>k+'='+(v.includes(String.fromCharCode(10))||v.includes(String.fromCharCode(13))||v.startsWith('"')?JSON.stringify(v):v)).join(String.fromCharCode(10))}
function parseEnvLines(text){const env={};for(const line of text.split(String.fromCharCode(10))){if(!line.trim())continue;const i=line.indexOf('=');if(i<1)throw Error('Environment lines must be KEY=value');let value=line.slice(i+1);if(value.startsWith('"')){try{value=JSON.parse(value)}catch(e){throw Error('Quoted value for '+line.slice(0,i)+' must be a JSON string')}}env[line.slice(0,i).trim()]=value}return env}
function editLines(text){return text.split(String.fromCharCode(10)).map(l=>l.trim()).filter(Boolean)}
async function saveResources(id,values){return call('containers/'+encodeURIComponent(id)+'/resources','POST',values)}
async function renameContainer(id,newName){return call('containers/'+encodeURIComponent(id)+'/rename','POST',{name:newName})}
async function recreateContainer(id,body){return call('containers/'+encodeURIComponent(id)+'/recreate','POST',body)}
async function rollbackContainer(id){return call('containers/'+encodeURIComponent(id)+'/rollback','POST',{})}
async function setupEditWorkspace(content,id,name){
 const spec=await call('containers/'+encodeURIComponent(id)+'/edit');content.replaceChildren();
 const status=editEl('p',{className:'tool-status'});status.setAttribute('aria-live','polite');
 const done=async(message,newId,newName)=>{status.textContent=message;try{await listContainers()}catch(e){}viewContainerDetails(newId||id,newName||name,'','edit')};
 const guard=fn=>async()=>{status.textContent='Working…';try{await fn()}catch(e){status.textContent=e.message}};
 const memory=editEl('input',{type:'number',min:16,placeholder:'MiB (empty = keep)',value:spec.memory_mb??''});
 const cpus=editEl('input',{type:'number',min:0.01,step:0.01,placeholder:'CPU cores (empty = keep)',value:spec.nano_cpus?spec.nano_cpus/1e9:''});
 const restart=editEl('select',{},['no','always','unless-stopped','on-failure'].map(v=>editEl('option',{value:v,textContent:v,selected:v===spec.restart})));
 const memoryValue=()=>memory.value?Number(memory.value):null;const cpusValue=()=>cpus.value?Math.round(Number(cpus.value)*1e9):null;
 const memoryChanged=()=>memoryValue()===(spec.memory_mb??null)?null:memoryValue();const cpusChanged=()=>cpusValue()===(spec.nano_cpus??null)?null:cpusValue();
 const live=()=>({memory_mb:memoryChanged(),nano_cpus:cpusChanged(),restart:restart.value});
 const newName=editEl('input',{value:spec.name});const network=editEl('input',{placeholder:'network name'});
 content.append(editEl('h4',{textContent:'Live settings (no restart)'}),editField('Memory limit',memory),editField('CPU limit',cpus),editField('Restart policy',restart),
  makeToolButton('Save live settings',guard(async()=>{await saveResources(id,live());await done('Live settings saved')})),
  editField('Name',newName),makeToolButton('Rename',guard(async()=>{const r=await renameContainer(id,newName.value.trim());await done('Renamed',id,r.name)})),
  editField('Network',network),
  makeToolButton('Connect',guard(async()=>{await call('containers/'+encodeURIComponent(id)+'/networks/'+encodeURIComponent(network.value.trim())+'/connect','POST',{});await done('Connected to '+network.value.trim())})),
  makeToolButton('Disconnect',guard(async()=>{await call('containers/'+encodeURIComponent(id)+'/networks/'+encodeURIComponent(network.value.trim())+'/disconnect','POST',{});await done('Disconnected from '+network.value.trim())})));
 content.append(editEl('h4',{textContent:'Edit & recreate'}));
 if(spec.compose_project){
  content.append(editEl('p',{className:'hint',textContent:'Managed by Compose stack '+spec.compose_project+'. Edit the stack instead, so the next deploy keeps your changes.'}),makeToolButton('Open Compose stacks',()=>navigate('compose')));
 }else{
  const image=editEl('input',{value:spec.image||''});
  const command=editEl('input',{placeholder:'JSON array, empty = image default',value:formatCommand(spec.command)});
  const env=editEl('textarea',{rows:4,value:formatEnv(spec.environment)});
  const ports=editEl('textarea',{rows:3,placeholder:'8080:80, 0.0.0.0:443:443/tcp, *::80 (random), [::]:443:443',value:formatPortLines(spec.port_bindings)});
  const mounts=editEl('textarea',{rows:3,placeholder:'/host/path:/container/path or volume:/path[:ro]',value:(spec.mounts||[]).join(String.fromCharCode(10))});
  const ackRisk=editEl('input',{type:'checkbox'});const ackPublic=editEl('input',{type:'checkbox'});
  const body=pull=>({image:image.value.trim(),command:parseCommand(command.value),environment:parseEnvLines(env.value),port_bindings:parsePortLines(ports.value),mounts:editLines(mounts.value),memory_mb:memoryValue(),nano_cpus:cpusValue(),restart:restart.value,pull,acknowledge_high_risk:ackRisk.checked,acknowledge_public_ports:ackPublic.checked});
  const run=pull=>guard(async()=>{if(!confirm('Recreate '+name+'? It will be stopped and replaced; the old container is kept as a backup.'))return;status.textContent='Recreating…';const r=await recreateContainer(id,body(pull));await done('Recreated; backup '+r.backup,r.id,r.name)});
  content.append(editField('Image',image),editField('Command',command),editField('Environment (KEY=value per line)',env),editField('Ports',ports),editField('Mounts',mounts),
   editField('I accept host-level risk (bind mounts, privileged, host network)',ackRisk),editField('I accept exposing ports beyond localhost',ackPublic),
   makeToolButton('Save & recreate',run(false)),makeToolButton('Update image (pull & recreate)',run(true)));
 }
 if(spec.backup){
  content.append(editEl('h4',{textContent:'Backup'}),editEl('p',{textContent:'Previous container: '+spec.backup.old_name+' ('+new Date(spec.backup.created_at*1000).toLocaleString()+')'}),
   makeToolButton('Roll back',guard(async()=>{if(!confirm('Replace the current container with the backup?'))return;const r=await rollbackContainer(id);await done('Rolled back',r.id,r.name)})),
   makeToolButton('Remove backup',guard(async()=>{if(!confirm('Delete the backup container? Volumes are kept.'))return;await removeBackup(id);await done('Backup removed')})));
 }
 content.append(status);
}
async function removeBackup(id){return call('containers/'+encodeURIComponent(id)+'/backup','DELETE')}
let detailsFullscreen=false;document.addEventListener('keydown',event=>{if(event.key==='Escape'&&detailsFullscreen){detailsFullscreen=false;document.querySelector('#containerDetailPanel')?.classList.remove('fullscreen-details')}});
async function viewContainerDetails(id,name,state,tab='overview'){
 const panel=document.querySelector('#containerDetailPanel');panel.hidden=false;panel.replaceChildren();
 const header=document.createElement('div');header.className='detail-header';
 const heading=document.createElement('h3');heading.textContent=name+' · Details';
 const close=document.createElement('button');close.type='button';close.textContent='Close';close.onclick=()=>{panel.classList.remove('fullscreen-details');panel.hidden=true;panel.replaceChildren()};
 const maximize=document.createElement('button');maximize.type='button';maximize.textContent=detailsFullscreen?'Exit fullscreen':'Fullscreen';maximize.onclick=()=>{detailsFullscreen=!detailsFullscreen;panel.classList.toggle('fullscreen-details',detailsFullscreen);maximize.textContent=detailsFullscreen?'Exit fullscreen':'Fullscreen'};panel.classList.toggle('fullscreen-details',detailsFullscreen);
 header.append(heading,maximize,close);panel.append(header);
 const tabs=document.createElement('div');tabs.className='detail-tabs';tabs.setAttribute('role','tablist');
 const content=document.createElement('div');content.className='detail-content';content.setAttribute('aria-live','polite');content.textContent='Loading…';
 for(const type of ['overview','configuration','network','mounts','logs','stats','console','edit','raw']){
  const button=document.createElement('button');button.type='button';button.textContent=type==='raw'?'Raw JSON':type[0].toUpperCase()+type.slice(1);
  button.className=type===tab?'primary-action':'';button.setAttribute('role','tab');button.setAttribute('aria-selected',String(type===tab));
  button.onclick=()=>viewContainerDetails(id,name,state,type);tabs.append(button);
 }
 panel.append(tabs,content);
 try{
  if(['overview','configuration','network','mounts','raw'].includes(tab)){
   const data=await call('containers/'+encodeURIComponent(id));content.replaceChildren();renderInspectDetails(content,data,tab);
  }else if(tab==='logs'){
   if(!canOperate())content.textContent='Operator permission required.';else await setupLogWorkspace(content,id);
  }else if(tab==='stats'){
   const value=await call('containers/'+encodeURIComponent(id)+'/metrics');content.replaceChildren();
   content.append(detailsGroup('Live statistics',[['CPU',String(value.cpu_percent??'—')+'%'],['Memory',bytesHuman(value.memory_usage_bytes)],['Memory percent',String(value.memory_percent??'—')+'%'],['Network RX',String(value.network_rx_bytes??'—')+' bytes'],['Network TX',String(value.network_tx_bytes??'—')+' bytes']]));
  }else if(tab==='edit'){
   if(!canAdmin())content.textContent='Admin permission required.';else await setupEditWorkspace(content,id,name);
  }else if(tab==='console'){
   if(!canOperate())content.textContent='Operator permission required.';else setupConsoleWorkspace(content,id);
  }
 }catch(e){content.textContent=e.message}
 panel.scrollIntoView({behavior:'smooth',block:'nearest'});
}
async function operate(id,action){try{await call('containers/'+encodeURIComponent(id)+'/'+action,'POST');await listContainers()}catch(err){alert(err.message)}}
function addPortRow(){
 const template=document.querySelector('.portRow');const row=template.cloneNode(true);
 row.querySelectorAll('input').forEach(el=>{el.value=el.classList.contains('hostIP')?'127.0.0.1':''});
 document.querySelector('#portRows').append(row);
}
async function createContainer(startNow=false){
 try{if(!canAdmin())throw Error('Requires Admin');
   const name=document.querySelector('#newName').value.trim();const image=document.querySelector('#newImage').value.trim();
   const privileged=document.querySelector('#highRisk').checked;
   const acknowledge_high_risk=document.querySelector('#ackRisk').checked;
   const port_bindings=[];
   for(const row of document.querySelectorAll('.portRow')){
     const host_port=row.querySelector('.hostPort').value.trim();
     const container_port=row.querySelector('.containerPort').value.trim();
     if(!host_port&&!container_port)continue;
     if(!host_port||!container_port)throw Error('Both host and container ports are required');
     port_bindings.push({host_ip:row.querySelector('.hostIP').value.trim()||'127.0.0.1',host_port:Number(host_port),container_port:Number(container_port),protocol:row.querySelector('.portProtocol').value});
   }
   const acknowledge_public_ports=document.querySelector('#publicPorts').checked;
   if(port_bindings.some(p=>p.host_ip!=='127.0.0.1')&&!acknowledge_public_ports)throw Error('Non-localhost port binding requires exposure acknowledgement');
   const restart=document.querySelector('#newRestart').value;
   const memoryText=document.querySelector('#newMemory').value.trim();
   const memory_mb=memoryText?Number(memoryText):null;
   if(memoryText&&(!Number.isInteger(memory_mb)||memory_mb<16||memory_mb>1048576))throw Error('Memory limit must be an integer between 16 and 1048576 MiB');
   const environment={};
   for(const [index,line] of document.querySelector('#newEnvironment').value.split(String.fromCharCode(10)).entries()){
      if(!line.trim())continue;
      const pos=line.indexOf('=');const key=line.slice(0,pos).trim();
      if(pos<1||!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key))throw Error('Invalid environment variable at line '+(index+1)+'; use KEY=value');
      if(Object.hasOwn(environment,key))throw Error('Duplicate environment key: '+key);
      environment[key]=line.slice(pos+1);
   }
   const mounts=document.querySelector('#newMounts').value.split(String.fromCharCode(10)).map(x=>x.trim()).filter(Boolean);
   for(const mount of mounts){const parts=mount.split(':');if(parts.length<2||parts.length>3||!parts[0].startsWith('/')||!parts[1].startsWith('/')||(parts.length===3&&!['ro','rw'].includes(parts[2])))throw Error('Invalid bind mount: '+mount)}
   if((privileged||mounts.length>0)&&!acknowledge_high_risk)throw Error('Host risk acknowledgement is required for privileged mode or bind mounts');
   await call(startNow?'containers/create-and-start':'containers','POST',{name,image,privileged,acknowledge_high_risk,port_bindings,acknowledge_public_ports,restart,memory_mb,environment,mounts});
   document.querySelector('#containerMsg').textContent=startNow?'Container created and started':'Container created (not started)';await listContainers()
 }catch(err){document.querySelector('#containerMsg').textContent=err.message}
}
async function deleteContainer(id,name){
 if(!confirm('Delete container '+name+'? This cannot be undone.'))return;
 const exact=prompt('Type the exact container ID to confirm deletion: '+id);
 if(exact!==id){alert('Confirmation mismatch');return}
 try{await call('containers/'+encodeURIComponent(id),'DELETE',{confirm_name:id});await listContainers()}
 catch(err){alert(err.message)}
}

async function resourcePage(kind){
 const panel=document.querySelector('#resourcePanel');panel.replaceChildren();
 const heading=document.createElement('h3');heading.textContent=kind[0].toUpperCase()+kind.slice(1);panel.appendChild(heading);
 const data=await call('docker/'+kind);
 const input=document.createElement('input');input.placeholder=kind==='images'?'Image reference (nginx:alpine)':'New '+kind.slice(0,-1)+' name';panel.appendChild(input);
 if(canAdmin()){
  const create=document.createElement('button');create.textContent=kind==='images'?'Pull Image':'Create '+kind.slice(0,-1);
  create.onclick=async()=>{try{const path=kind==='images'?'images/pull':kind;await call(path,'POST',kind==='images'?{image:input.value.trim()}:{name:input.value.trim()});await resourcePage(kind)}catch(err){alert(err.message)}};
  panel.appendChild(create);
 }
 for(const item of data.items){
  const ident=kind==='images'?(item.RepoTags||[]).find(t=>t!=='<none>:<none>')||item.Id:kind==='networks'?item.Name:item.Name;
  const div=document.createElement('div');div.style.cssText='padding:10px;border-bottom:1px solid #435575';
  const span=document.createElement('span');span.textContent=String(ident)+' ';div.appendChild(span);
  if(canAdmin() && ident){
   const button=document.createElement('button');button.textContent='Delete';
   button.onclick=async()=>{if(!confirm('Delete '+ident+'?'))return;const exact=prompt('Type exact resource name/reference to delete: '+ident);if(exact!==ident)return;
    try{await call(kind+'/'+encodeURIComponent(ident),'DELETE',{confirm_name:ident});await resourcePage(kind)}catch(err){alert(err.message)}};
   div.appendChild(button);
  }
  panel.appendChild(div);
 }
}

let logsTimer=null,selectedLogId=null;
function stopLogsRefresh(){if(logsTimer){clearInterval(logsTimer);logsTimer=null}}
async function fetchSelectedLogs(){if(!selectedLogId)return;try{const r=await call('containers/'+encodeURIComponent(selectedLogId)+'/logs?tail=150');document.querySelector('#logOutput').textContent=r.output||'(no logs)'}catch(e){document.querySelector('#logOutput').textContent=e.message}}
async function viewLogs(id){stopLogsRefresh();selectedLogId=id;const panel=document.querySelector('#logsPanel');panel.replaceChildren();const title=document.createElement('h3');title.textContent='Container logs (last 150 lines)';const pre=document.createElement('pre');pre.id='logOutput';const btn=document.createElement('button');btn.textContent='Refresh logs';btn.onclick=fetchSelectedLogs;const label=document.createElement('label');const check=document.createElement('input');check.type='checkbox';check.onchange=()=>{stopLogsRefresh();if(check.checked){logsTimer=setInterval(()=>{if(!document.hidden)fetchSelectedLogs()},5000)}};label.append(check,document.createTextNode(' Auto-refresh logs (5s)'));panel.append(title,btn,label,pre);await fetchSelectedLogs()}
let metricsTimer=null,monitorBusy=false,selectedHistory=null,historyWindow='1h',historyLastFetch=0,historyInFlight=false;
function toggleMetricsRefresh(){if(metricsTimer){clearInterval(metricsTimer);metricsTimer=null}if(document.querySelector('#metricsRefresh').checked){const fast=document.querySelector('#fastDisplay');const ms=fast&&fast.checked?1000:5000;metricsTimer=setInterval(()=>{if(!document.hidden&&!document.querySelector('#monitorPanel').hidden){refreshMonitor();refreshHostMetrics()}},ms)}}
function humanSize(n){const num=Number(n)||0;return (num/1073741824).toFixed(2)+' GiB'}
async function refreshHostMetrics(){const panel=document.getElementById('hostMetrics');if(!panel)return;try{const d=await call('system/host');const memUsed=Math.max(0,d.memory_total_bytes-d.memory_available_bytes);const diskUsed=d.root_disk_total_bytes-d.root_disk_free_bytes;const details=[['Host load (1m)',d.load_1m+' / '+d.cpu_cores+' cores'],['RAM',humanSize(memUsed)+' / '+humanSize(d.memory_total_bytes)],['Root disk',humanSize(diskUsed)+' / '+humanSize(d.root_disk_total_bytes)],['Network interfaces',Object.keys(d.network_interfaces||{}).length]];panel.replaceChildren();for(const [name,value] of details){const card=document.createElement('div');card.className='host-stat';const label=document.createElement('span');label.textContent=name;const strong=document.createElement('strong');strong.textContent=value;card.append(label,strong);panel.append(card)}}catch(e){panel.textContent='Host statistics unavailable: '+e.message}}
async function dashboardPage(){refreshHostMetrics();document.querySelector('#monitorPanel').hidden=false;await refreshMonitor()}
function fmtBytes(n){if(!Number.isFinite(n)||n<0)return '—';if(n<1024)return n+' B';const units=['KiB','MiB','GiB','TiB'];let i=-1;do{n/=1024;i++}while(n>=1024&&i<units.length-1);return n.toFixed(1)+' '+units[i]}
async function refreshMonitor(){
 if(monitorBusy)return;monitorBusy=true;
 const summary=document.querySelector('#monitorSummary'),rows=document.querySelector('#monitorRows');
 try{
  const [dash,containers]=await Promise.all([call('dashboard'),call('docker/containers')]);
  const statusBox=document.querySelector('#collectorHealth');
  try{const cs=await call('monitoring/collector');statusBox.textContent='Collector: '+(cs.active?'active':'stale/offline')+' · state: '+cs.state+' · last attempt: '+(cs.age_seconds??'unknown')+'s ago · last success: '+(cs.last_success_age_seconds??'unknown')+'s ago · collected: '+(cs.collected??0)+' / '+(cs.running??0)+' · errors: '+(cs.failed??0)+' · cycle: '+(cs.duration_ms??'—')+'ms · interval: '+(cs.interval_seconds??5)+'s · alerts: '+(cs.alert_count??0)+(cs.overrun?' · OVERRUN':'')}catch(_){statusBox.textContent='Collector health unavailable'}
  summary.replaceChildren();for(const [title,value] of [['Total',dash.containers],['Running',dash.running],['Stopped',dash.stopped],['Paused',dash.paused]]){const card=document.createElement('div');card.className='metric-card';const number=document.createElement('b');number.textContent=String(value??0);const caption=document.createElement('span');caption.textContent=title;card.append(number,caption);summary.append(card)}
  const items=(containers.items||[]).slice(0,60);const snap=[];
  // Bounded concurrency avoids bursting the Docker Engine when many containers exist.
  for(let i=0;i<items.length;i+=4){
    const batch=await Promise.all(items.slice(i,i+4).map(async c=>{
      if(c.State!=='running')return {c};
      try{return {c,m:await call('containers/'+encodeURIComponent(c.Id)+'/metrics')}}catch(e){return {c,error:e.message}}
    }));snap.push(...batch);
  }
  rows.replaceChildren();
  for(const {c,m,error} of snap){
    const raw=((c.Names||[])[0]||c.Id),name=raw.startsWith('/')?raw.slice(1):raw;
    const div=document.createElement('div');div.className='container-card';
    const dot=document.createElement('span');dot.className='status-dot'+(c.State==='running'?'':' off');const head=document.createElement('strong');head.textContent=name+' — '+c.State;div.append(dot,head);
    const line=document.createElement('div');
    line.textContent=m?'CPU '+m.cpu_percent.toFixed(2)+'% · RAM '+fmtBytes(m.memory_usage_bytes)+' / '+fmtBytes(m.memory_limit_bytes)+' ('+m.memory_percent.toFixed(1)+'%) · RX '+(m.network_rx_bps/1e6).toFixed(3)+' Mbps · TX '+(m.network_tx_bps/1e6).toFixed(3)+' Mbps · Totals '+fmtBytes(m.network_rx_bytes)+' / '+fmtBytes(m.network_tx_bytes):error||'Not running';
    div.append(line);
    if(m){const btn=document.createElement('button');btn.textContent='History';btn.onclick=()=>{selectedHistory={id:c.Id,name};showHistory()};div.append(btn)}
    rows.append(div)
  }
  document.querySelector('#data').textContent=JSON.stringify(dash,null,2);
  if(selectedHistory && Date.now()-historyLastFetch>=10000)await showHistory();
 }catch(e){summary.textContent=e.message}finally{monitorBusy=false}
}
function drawSpark(points,key,title,scale){
 const wrap=document.createElement('div');wrap.className='chart-panel';
 const label=document.createElement('strong');label.textContent=title;wrap.append(label);
 const subtitle=document.createElement('div');subtitle.style.cssText='font-size:12px;color:#a7bbd5;margin:4px 0';subtitle.textContent='Move pointer over chart to inspect a sample';wrap.append(subtitle);
 const canvas=document.createElement('canvas');canvas.width=640;canvas.height=190;canvas.setAttribute('role','img');canvas.setAttribute('aria-label',title+' historical time series');wrap.append(canvas);
 const ctx=canvas.getContext('2d');if(!ctx)return wrap;
 const vals=points.map(p=>Math.max(0,Number(p[key])||0)/scale);const max=Math.max(0.001,...vals)*1.1;
 const L=58,R=618,T=20,B=152;
 function paint(selected=-1){ctx.clearRect(0,0,640,190);ctx.strokeStyle='#48617e';ctx.lineWidth=1;ctx.fillStyle='#acbfd9';ctx.font='12px system-ui';
   for(let j=0;j<=3;j++){const y=B-j*(B-T)/3;ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(R,y);ctx.stroke();ctx.fillText((j*max/3).toFixed(2),6,y+4)}
   if(!vals.length){ctx.fillText('No recorded samples yet',L+12,85);return}
   const low=Number(points[0].ts)*1000,high=Number(points[points.length-1].ts)*1000;
   ctx.fillText(new Date(low).toLocaleTimeString(),L,177);const right=new Date(high).toLocaleTimeString();ctx.fillText(right,R-ctx.measureText(right).width,177);
   ctx.strokeStyle='#80b7ff';ctx.lineWidth=2;ctx.beginPath();vals.forEach((v,i)=>{const x=L+(vals.length===1?0:i/(vals.length-1)*(R-L)),y=B-v/max*(B-T);if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y)});ctx.stroke();
   if(selected>=0){const x=L+(vals.length===1?0:selected/(vals.length-1)*(R-L)),y=B-vals[selected]/max*(B-T);ctx.fillStyle='#ffcf75';ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fill();subtitle.textContent=new Date(Number(points[selected].ts)*1000).toLocaleString()+' · '+vals[selected].toFixed(3)}}
 paint();canvas.addEventListener('pointermove',e=>{if(!vals.length)return;const rect=canvas.getBoundingClientRect();const x=(e.clientX-rect.left)*canvas.width/rect.width;const i=Math.max(0,Math.min(vals.length-1,Math.round((x-L)/(R-L)*(vals.length-1))));paint(i)});canvas.addEventListener('pointerleave',()=>{subtitle.textContent='Move pointer over chart to inspect a sample';paint()});
 return wrap;
}
async function showHistory(){
 if(!selectedHistory||historyInFlight)return;historyInFlight=true;
 const selected=selectedHistory,window=historyWindow;
 const panel=document.querySelector('#historyPanel');panel.replaceChildren();
 const title=document.createElement('h4');title.textContent='History: '+selected.name;panel.append(title);
 for(const w of ['1h','24h','7d','30d','90d']){const b=document.createElement('button');b.textContent=w;b.disabled=window===w;b.onclick=()=>{historyWindow=w;historyLastFetch=0;showHistory()};panel.append(b)}
 try{const r=await call('containers/'+encodeURIComponent(selected.id)+'/metrics/history?window='+window);
 if(selectedHistory?.id!==selected.id||historyWindow!==window)return;
 const info=document.createElement('p');info.textContent=r.sample_count+' samples · '+r.note;panel.append(info);
 const grid=document.createElement('div');grid.className='chart-grid';
 grid.append(drawSpark(r.points,'cpu_percent','CPU (%)',1),drawSpark(r.points,'memory_usage_bytes','RAM (MiB)',1048576),drawSpark(r.points,'network_rx_bps','RX (Mbps)',1e6),drawSpark(r.points,'network_tx_bps','TX (Mbps)',1e6));panel.append(grid);historyLastFetch=Date.now();
 }catch(e){const msg=document.createElement('p');msg.textContent=e.message;panel.append(msg)}finally{historyInFlight=false}
}

function commandPanel(id){const root=document.querySelector('#consolePanel');root.replaceChildren();const h=document.createElement('h3');h.textContent='One-shot container command (not a live TTY)';const inp=document.createElement('input');inp.placeholder='Command (e.g. id or ls /)';inp.style.width='70%';const run=document.createElement('button');run.textContent='Execute';const msg=document.createElement('pre');run.onclick=async()=>{const argv=inp.value.trim().split(/\\s+/).filter(Boolean);if(!argv.length)return;try{const r=await call('containers/'+encodeURIComponent(id)+'/exec','POST',{argv});msg.textContent=r.output||'(empty output)'}catch(e){msg.textContent=e.message}};root.append(h,inp,run,msg)}
async function stackPage(){
 const panel=document.querySelector('#stackPanel');panel.replaceChildren();const h=document.createElement('h3');h.textContent='Compose Stacks';panel.append(h);
 const editor=document.createElement('section');editor.className='compose-editor';const name=document.createElement('input');name.placeholder='Stack name';name.setAttribute('aria-label','Stack name');const y=document.createElement('textarea');y.rows=13;y.placeholder='Paste Compose YAML';y.setAttribute('aria-label','Compose YAML');const ack=document.createElement('input');ack.type='checkbox';const label=document.createElement('label');label.append(ack,document.createTextNode(' I acknowledge that Compose can access host resources'));
 const mode=document.createElement('span');mode.textContent='New stack';const save=document.createElement('button');save.textContent='Save & validate';let editing=false;
 const reset=()=>{editing=false;mode.textContent='New stack';name.readOnly=false;name.value='';y.value='';ack.checked=false;save.textContent='Save & validate'};
 save.onclick=async()=>{if(!canAdmin())return;try{const payload={name:name.value.trim(),yaml:y.value,acknowledge_host_risk:ack.checked};await call(editing?'stacks/'+encodeURIComponent(name.value.trim())+'/definition':'stacks',editing?'PUT':'POST',payload);await stackPage()}catch(e){alert(e.message)}};
 const cancel=document.createElement('button');cancel.textContent='Cancel edit';cancel.onclick=reset;
 if(canAdmin()){editor.append(mode,name,y,label,save,cancel);panel.append(editor)}
 try{const r=await call('stacks');for(const item of r.items){const line=document.createElement('div');line.className='compose-stack-row';const t=document.createElement('strong');t.textContent=item.name+' · '+(item.project||'df_'+item.name);line.append(t);
 if(canAdmin()){const edit=document.createElement('button');edit.textContent='Edit YAML';edit.onclick=async()=>{try{const def=await call('stacks/'+encodeURIComponent(item.name)+'/definition');editing=true;mode.textContent='Editing '+def.name+' (save validates only; deploy separately)';name.value=def.name;name.readOnly=true;y.value=def.yaml;ack.checked=false;save.textContent='Validate & save changes';editor.scrollIntoView({behavior:'smooth',block:'start'})}catch(e){alert(e.message)}};line.append(edit)}
 if(canAdmin())for(const act of ['up','stop','start','down']){const b=document.createElement('button');b.textContent=act;b.onclick=async()=>{if(act==='down'&&!confirm('Stop and remove stack containers and network?'))return;try{await call('stacks/'+encodeURIComponent(item.name)+'/'+act,'POST');await stackPage()}catch(e){alert(e.message)}};line.append(b)}panel.append(line)}}catch(e){const msg=document.createElement('p');msg.textContent=e.message;panel.append(msg)}
}
async function logout(){try{await call('auth/logout','POST')}catch(e){}location.reload()}

const viewLabels={dashboard:['Overview','Container health, resources, and host activity at a glance.'],containers:['Containers','Create, inspect and control your workloads.'],images:['Images','Pull and manage local container images.'],networks:['Networks','Manage isolated Docker network resources.'],volumes:['Volumes','Persistent container storage resources.'],compose:['Compose stacks','Deploy and control multi-container applications.'],alerts:['Alert management','Per-container rules, incidents, acknowledgement and delivery.'],diagnostics:['Diagnostics','Read-only health checks and diagnostic output.'],users:['User management','Super Admin access control, credentials and session revocation.'],backups:['Backup center','Read-only application, volume and bind archive inventory.'],audit:['Audit trail','Review privileged host management operations.'],raw:['Raw containers','Docker Engine container inventory in JSON.']};
let activeView='dashboard';
async function usersPage(){
 const pane=document.querySelector('#resourcePanel');pane.replaceChildren();
 if(currentRole!=='super_admin'){pane.textContent='Super Admin access required';return}
 const heading=document.createElement('h3');heading.textContent='User management';pane.appendChild(heading);
 const notice=document.createElement('p');notice.textContent='Role changes, password resets and deletion revoke the affected user’s active sessions.';pane.appendChild(notice);
 const rows=await call('users');
 for(const user of rows.items||[]){
   const line=document.createElement('div');line.className='workload-row';line.style.marginBottom='9px';
   const label=document.createElement('strong');label.textContent=user.username+' · '+user.role;line.appendChild(label);
   const role=document.createElement('select');for(const r of ['viewer','operator','admin','super_admin']){const opt=document.createElement('option');opt.value=r;opt.textContent=r;role.append(opt)}role.value=user.role;
   const change=document.createElement('button');change.textContent='Update role';change.onclick=async()=>{if(!confirm('Change '+user.username+' to '+role.value+'?'))return;try{await call('users/'+user.id+'/role','PUT',{role:role.value});await usersPage()}catch(e){alert(e.message)}};
   const reset=document.createElement('button');reset.textContent='Reset password';reset.onclick=async()=>{const pass=prompt('New password (minimum 12 characters)');if(pass===null)return;try{await call('users/'+user.id+'/password','PUT',{password:pass});await usersPage()}catch(e){alert(e.message)}};
   const del=document.createElement('button');del.textContent='Delete';del.onclick=async()=>{if(!confirm('Permanently delete user '+user.username+'?'))return;try{await call('users/'+user.id,'DELETE');await usersPage()}catch(e){alert(e.message)}};
   const sessions=document.createElement('button');sessions.textContent='Sessions';sessions.onclick=async()=>{try{const res=await call('users/'+user.id+'/sessions');alert(user.username+' has '+res.count+' active session(s)')}catch(e){alert(e.message)}};
   const revoke=document.createElement('button');revoke.textContent='Revoke sessions';revoke.onclick=async()=>{if(!confirm('Sign out all sessions for '+user.username+'?'))return;try{const res=await call('users/'+user.id+'/revoke-sessions','POST',{});alert('Revoked '+res.revoked+' session(s)');await usersPage()}catch(e){alert(e.message)}};
   line.append(role,change,reset,sessions,revoke,del);pane.appendChild(line);
 }
 const header=document.createElement('h4');header.textContent='Create user';pane.appendChild(header);
 const name=document.createElement('input');name.placeholder='Username';name.autocomplete='off';
 const password=document.createElement('input');password.type='password';password.placeholder='Password (12+ characters)';password.autocomplete='new-password';
 const role=document.createElement('select');for(const r of ['viewer','operator','admin','super_admin']){const opt=document.createElement('option');opt.value=r;opt.textContent=r;role.append(opt)}
 const create=document.createElement('button');create.textContent='Create user';create.onclick=async()=>{try{await call('users','POST',{username:name.value,password:password.value,role:role.value});password.value='';await usersPage()}catch(e){alert(e.message)}};
 pane.append(name,password,role,create);
}

async function backupsPage(){
 const pane=document.getElementById('resourcePanel');pane.replaceChildren();
 const heading=document.createElement('h3');heading.textContent='Backup & Recovery Center';pane.append(heading);
 const note=document.createElement('p');note.textContent='Read-only inventory. No archive is downloaded and no restore is executed from this screen.';pane.append(note);
 try{
  const data=await call('backups/overview');const cfg=data.configuration;
  const summary=document.createElement('section');
  const h=document.createElement('h4');h.textContent='Persistent data schedule';summary.append(h);
  const p=document.createElement('p');p.textContent='Config available: '+cfg.available+' · Enabled: '+cfg.enabled+' · Retention: '+(cfg.keep??'unknown')+' · Volume targets: '+cfg.volumes.length+' · Bind targets: '+cfg.binds.length;summary.append(p);
  const n=document.createElement('p');n.textContent=data.note;summary.append(n);pane.append(summary);
  const count=document.createElement('h4');count.textContent='Backup archive inventory ('+data.archive_count+')';pane.append(count);
  const tbl=document.createElement('table');tbl.style.width='100%';tbl.innerHTML='<thead><tr><th>Type</th><th>Archive</th><th>Size</th><th>Modified</th></tr></thead>';
  const tbody=document.createElement('tbody');for(const item of data.archives){const tr=document.createElement('tr');for(const value of [item.kind,item.name,(item.bytes/1048576).toFixed(2)+' MiB',new Date(item.modified*1000).toLocaleString()]){const td=document.createElement('td');td.textContent=value;td.style.padding='8px';td.style.overflowWrap='anywhere';tr.append(td)}tbody.append(tr)}tbl.append(tbody);pane.append(tbl);
  if(!data.archives.length){const p=document.createElement('p');p.textContent='No accessible backup archives. Root-only archives may not be visible to the web service.';pane.append(p)}
 }catch(e){const p=document.createElement('p');p.textContent='Unable to load Backup Center: '+e.message;pane.append(p)}
}
async function navigate(view){
 if(!viewLabels[view])return;
 activeView=view;
 const targets=['monitorPanel','containerPanel','resourcePanel','stackPanel','consolePanel','logsPanel'];
 for(const id of targets){const el=document.getElementById(id);el.hidden=true}
 const data=document.getElementById('diagnosticsDetail');data.open=view==='raw'||view==='diagnostics'||view==='audit';
 document.getElementById('pageTitle').textContent=viewLabels[view][0];
 document.getElementById('pageDescription').textContent=viewLabels[view][1];
 document.getElementById('breadcrumb').textContent=viewLabels[view][0].toUpperCase();
 document.querySelectorAll('.nav-links button[data-view]').forEach(el=>{const active=el.dataset.view===view;el.classList.toggle('active',active);if(active)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current')});
 if(view==='dashboard'){document.getElementById('monitorPanel').hidden=false;await dashboardPage()}
 else if(view==='containers'){document.getElementById('containerPanel').hidden=false;await listContainers()}
 else if(['images','networks','volumes'].includes(view)){document.getElementById('resourcePanel').hidden=false;await resourcePage(view)}
 else if(view==='compose'){document.getElementById('stackPanel').hidden=false;await stackPage()}
 else if(view==='alerts'){document.getElementById('resourcePanel').hidden=false;await alertRulesPage()}
 else if(view==='diagnostics'){await loadData('system/diagnostics')}
 else if(view==='backups'){document.getElementById('resourcePanel').hidden=false;await backupsPage()}
 else if(view==='users'){document.getElementById('resourcePanel').hidden=false;await usersPage()}
 else if(view==='audit'){await loadData('audit')}
 else if(view==='raw'){await loadData('docker/containers')}
}
const originalShow=show;show=function(user){currentRole=user.role;document.querySelector('#auth').textContent='Signed in as '+user.username+' ('+user.role+')';document.querySelector('#panel').hidden=false;navigate('dashboard')};
// Legacy entry points are routed into the single structured Details workspace.
// Keep the old panels hidden to avoid duplicate log fetches and duplicated UI.
function openDetailsFor(id,tab){
 stopLogsRefresh();selectedLogId=null;
 for(const panelId of ['logsPanel','consolePanel']){const element=document.getElementById(panelId);if(element){element.hidden=true;element.replaceChildren()}}
 const item=(window.lastContainerList||[]).find(c=>c.Id===id||c.Id?.startsWith(id));
 const name=(item?.Names?.[0]||'').replace(/^[/]/,'')||id.slice(0,12);
 return viewContainerDetails(id,name,item?.State||'unknown',tab);
}
commandPanel=function(id){return openDetailsFor(id,'console')};
viewLogs=function(id){return openDetailsFor(id,'logs')};

const ACTIONS={
 navigate:(el)=>navigate(el.dataset.view),
 'refresh-view':()=>navigate(activeView),
 logout:()=>logout(),
 'refresh-monitor':()=>refreshMonitor(),
 'toggle-metrics':()=>toggleMetricsRefresh(),
 'list-containers':()=>listContainers(),
 'filter-containers':()=>filterContainerRows(),
 'add-port':()=>addPortRow(),
 'remove-port':(el)=>removePortRow(el),
 'create-container':(el)=>createContainer(el.dataset.start==='1'),
 login:()=>login(),
 setup:()=>setup()
};
// Inline event-handler attributes are blocked by the nonce-based CSP, so every static
// control declares data-action and is dispatched here instead.
['click','change','input'].forEach(type=>document.addEventListener(type,event=>{
 const el=event.target&&event.target.closest&&event.target.closest('[data-action]');
 if(!el)return;
 const action=ACTIONS[el.dataset.action];
 if(action)action(el,event)
}));
init().catch(e=>document.querySelector('#auth').textContent=e.message)
</script></body></html>'''
