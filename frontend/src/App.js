import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import axios from 'axios';
import {
  Play, Activity, List, Map as MapIcon, TrendingDown,
  Clock, Route, Box, Upload, RotateCcw, Award
} from 'lucide-react';
import './App.css';

const API_BASE = "http://127.0.0.1:8000";

// ─── Canvas Network Graph (dynamic — driven by API data) ──────────────────────
const NetworkGraph = ({ graphData, selectedRoute, startNode }) => {
  const canvasRef = useRef(null);
  const wrapRef   = useRef(null);
  const stateRef  = useRef({ route: null, startNode: 'A', hoveredEdge: null });
  const tipRef    = useRef(null);

  const nodes = useMemo(() => graphData?.nodes?.map(n => n.data.id) || [], [graphData]);
  const edges = useMemo(() => graphData?.edges?.map(e => e.data)   || [], [graphData]);
  const hasCoords = graphData?.has_coords;

  // Position: use actual TSPLIB coords if available, else circular layout
  const nodePos = useCallback((id, W, H) => {
    const node = graphData?.nodes?.find(n => n.data.id === id);
    if (hasCoords && node?.data?.x != null) {
      // Normalize TSPLIB coords to canvas
      const allX = graphData.nodes.map(n => n.data.x);
      const allY = graphData.nodes.map(n => n.data.y);
      const minX = Math.min(...allX), maxX = Math.max(...allX);
      const minY = Math.min(...allY), maxY = Math.max(...allY);
      const pad = 60;
      const nx = minX === maxX ? 0.5 : (node.data.x - minX) / (maxX - minX);
      const ny = minY === maxY ? 0.5 : (node.data.y - minY) / (maxY - minY);
      return { x: pad + nx * (W - pad*2), y: pad + ny * (H - pad*2) };
    }
    const i = nodes.indexOf(id);
    const n = nodes.length;
    const angle = (i / n) * 2 * Math.PI - Math.PI / 2;
    const r = Math.min(W, H) * 0.36;
    return { x: W/2 + r * Math.cos(angle), y: H/2 + r * Math.sin(angle) };
  }, [nodes, graphData, hasCoords]);

  const isEdgeInRoute = (s, t, route) => {
    if (!route) return false;
    for (let i = 0; i < route.length; i++) {
      const a = route[i], b = route[(i+1) % route.length];
      if ((a===s && b===t) || (a===t && b===s)) return true;
    }
    return false;
  };

  const draw = useCallback(() => {
    const canvas = canvasRef.current, wrap = wrapRef.current;
    if (!canvas || !wrap || !nodes.length) return;
    const W = canvas.width = wrap.clientWidth;
    const H = canvas.height = wrap.clientHeight;
    const ctx = canvas.getContext('2d');
    const { route, startNode: sn, hoveredEdge } = stateRef.current;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, W, H);

    const TYPE_COLOR = {
      highway: '#6366f1', local: '#0ea5e9',
      scenic: '#10b981',  bridge: '#8b5cf6', tsplib: '#0ea5e9',
    };
    const nodeR = nodes.length <= 8 ? 22 : nodes.length <= 20 ? 16 : 11;
    const fontSize = nodes.length <= 8 ? 14 : nodes.length <= 20 ? 11 : 9;

    // ── Edges ──
    edges.forEach(edge => {
      const p1 = nodePos(edge.source, W, H), p2 = nodePos(edge.target, W, H);
      if (!p1 || !p2) return;
      const inRoute = isEdgeInRoute(edge.source, edge.target, route);
      const isHov   = hoveredEdge === edge;
      const dx = p2.x-p1.x, dy = p2.y-p1.y, len = Math.hypot(dx, dy);
      if (len < 1) return;
      const nx = dx/len, ny = dy/len;
      const sx = p1.x + nx*nodeR, sy = p1.y + ny*nodeR;
      const ex = p2.x - nx*nodeR, ey = p2.y - ny*nodeR;

      const color = inRoute ? '#f43f5e' : isHov ? (TYPE_COLOR[edge.type] || '#0ea5e9') : 'rgba(59,130,246,0.18)';
      const lw    = inRoute ? 3.5 : isHov ? 2 : 1;

      if (inRoute) { ctx.shadowColor = '#f43f5e'; ctx.shadowBlur = 12; }
      ctx.beginPath();
      ctx.moveTo(sx, sy); ctx.lineTo(ex, ey);
      ctx.strokeStyle = color; ctx.lineWidth = lw; ctx.stroke();
      ctx.shadowBlur = 0;

      // Arrowhead on active route
      if (inRoute) {
        const ang = Math.atan2(ey-sy, ex-sx), sz = 9;
        const ax = ex - Math.cos(ang)*sz, ay = ey - Math.sin(ang)*sz;
        ctx.beginPath(); ctx.moveTo(ex, ey);
        ctx.lineTo(ax - Math.sin(ang)*sz*0.4, ay + Math.cos(ang)*sz*0.4);
        ctx.lineTo(ax + Math.sin(ang)*sz*0.4, ay - Math.cos(ang)*sz*0.4);
        ctx.closePath(); ctx.fillStyle = '#f43f5e'; ctx.fill();
      }

      // Weight badge (only for smaller graphs or hovered/active edges)
      if ((nodes.length <= 12 || inRoute || isHov) && len > nodeR*2) {
        const mid = { x:(p1.x+p2.x)/2, y:(p1.y+p2.y)/2 };
        const lbx = mid.x + (-ny)*14, lby = mid.y + nx*14;
        const label = `${edge.dist}`;
        ctx.font = `${inRoute?'600':'400'} 10px sans-serif`;
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        const tw = ctx.measureText(label).width + 8;
        ctx.fillStyle = inRoute ? '#4c0519' : isHov ? '#1e293b' : 'rgba(15,23,42,0.75)';
        ctx.beginPath(); ctx.roundRect(lbx-tw/2, lby-7, tw, 14, 3); ctx.fill();
        ctx.strokeStyle = inRoute ? '#f43f5e' : isHov ? (TYPE_COLOR[edge.type]||'#0ea5e9') : 'rgba(51,65,85,0.6)';
        ctx.lineWidth = 0.5; ctx.stroke();
        ctx.fillStyle = inRoute ? '#fb7185' : isHov ? '#e2e8f0' : '#64748b';
        ctx.fillText(label, lbx, lby);
      }
    });

    // ── Nodes ──
    nodes.forEach(id => {
      const pos = nodePos(id, W, H);
      if (!pos) return;
      const { x, y } = pos;
      const inRoute = route?.includes(id), isStart = id === sn;
      const r = isStart ? nodeR + 4 : nodeR;

      if (isStart) {
        ctx.beginPath(); ctx.arc(x, y, r+6, 0, Math.PI*2);
        ctx.fillStyle = 'rgba(16,185,129,0.15)'; ctx.fill();
        ctx.shadowColor = '#10b981'; ctx.shadowBlur = 18;
      } else if (inRoute) {
        ctx.shadowColor = '#3b82f6'; ctx.shadowBlur = 8;
      }

      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI*2);
      ctx.fillStyle = isStart ? '#059669' : inRoute ? '#1d4ed8' : '#1e293b';
      ctx.fill();
      ctx.strokeStyle = isStart ? '#34d399' : inRoute ? '#60a5fa' : '#334155';
      ctx.lineWidth = isStart || inRoute ? 2.5 : 1;
      ctx.stroke();
      ctx.shadowBlur = 0;

      ctx.font = `600 ${fontSize}px sans-serif`;
      ctx.fillStyle = '#f8fafc';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(id, x, y);

      if (isStart && nodeR >= 16) {
        ctx.font = '600 8px sans-serif';
        ctx.fillStyle = '#34d399';
        ctx.fillText('START', x, y + r + 10);
      }
    });
  }, [nodes, edges, nodePos]);

  const hitEdge = useCallback((mx, my, W, H) => {
    for (const edge of edges) {
      const p1 = nodePos(edge.source, W, H), p2 = nodePos(edge.target, W, H);
      if (!p1 || !p2) continue;
      const dx=p2.x-p1.x, dy=p2.y-p1.y, len=Math.hypot(dx,dy);
      const nx=dx/len, ny=dy/len;
      const proj=(mx-p1.x)*nx+(my-p1.y)*ny;
      if (proj < 0 || proj > len) continue;
      if (Math.abs((mx-p1.x)*(-ny)+(my-p1.y)*nx) < 10) return edge;
    }
    return null;
  }, [edges, nodePos]);

  useEffect(() => { stateRef.current.route = selectedRoute; draw(); }, [selectedRoute, draw]);
  useEffect(() => { stateRef.current.startNode = startNode; draw(); }, [startNode, draw]);
  useEffect(() => { draw(); }, [graphData, draw]);
  useEffect(() => {
    const ro = new ResizeObserver(draw);
    if (wrapRef.current) ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, [draw]);

  return (
    <div ref={wrapRef} className="ng-canvas-wrap"
      onMouseMove={e => {
        const rect = wrapRef.current.getBoundingClientRect();
        const mx = e.clientX-rect.left, my = e.clientY-rect.top;
        const W = canvasRef.current?.width||0, H = canvasRef.current?.height||0;
        const h = hitEdge(mx, my, W, H);
        if (h !== stateRef.current.hoveredEdge) { stateRef.current.hoveredEdge = h; draw(); }
        if (tipRef.current) {
          if (h) {
            tipRef.current.style.display = 'block';
            tipRef.current.style.left = Math.min(mx+14, W-175)+'px';
            tipRef.current.style.top  = Math.max(my-65, 6)+'px';
            tipRef.current.innerHTML  = `<b>${h.source} — ${h.target}</b>Dist: ${h.dist} km<br>Cost: $${h.cost}<br>Time: ${h.time} min<br><span class="ng-type-tag">${h.type}</span>`;
          } else tipRef.current.style.display = 'none';
        }
      }}
      onMouseLeave={() => {
        stateRef.current.hoveredEdge = null; draw();
        if (tipRef.current) tipRef.current.style.display = 'none';
      }}>
      <canvas ref={canvasRef} style={{ width:'100%', height:'100%' }} />
      {!nodes.length && (
        <div className="ng-empty">Loading graph…</div>
      )}
      <div ref={tipRef} className="ng-tip" />
    </div>
  );
};

// ─── 3D Cube Pareto Chart ─────────────────────────────────────────────────────
const ParetoChart3D = ({ solutions }) => {
  const canvasRef=useRef(null), wrapRef=useRef(null), tipRef=useRef(null);
  const stateRef=useRef({rotX:0.42,rotY:-0.62,zoom:1,dragging:false,lx:0,ly:0,hoveredIdx:-1});
  const projRef=useRef([]);

  const project=useCallback((x,y,z,W,H)=>{
    const{rotX,rotY,zoom}=stateRef.current;
    const cosX=Math.cos(rotX),sinX=Math.sin(rotX),cosY=Math.cos(rotY),sinY=Math.sin(rotY);
    const y2=y*cosX-z*sinX,z2=y*sinX+z*cosX;
    const x3=x*cosY+z2*sinY,z3=-x*sinY+z2*cosY;
    const scale=zoom*Math.min(W,H)*0.31,fov=3.5/(3.5+z3);
    return{sx:W/2+x3*scale*fov,sy:H/2-y2*scale*fov,z3};
  },[]);

  const norm=(v,mn,mx)=>mx===mn?0.5:(v-mn)/(mx-mn);

  const draw=useCallback(()=>{
    const canvas=canvasRef.current,wrap=wrapRef.current;
    if(!canvas||!wrap) return;
    const W=canvas.width=wrap.clientWidth,H=canvas.height=wrap.clientHeight;
    const ctx=canvas.getContext('2d');
    const proj=(x,y,z)=>project(x,y,z,W,H);
    const isDark=true;
    const CUBE_C=isDark?'rgba(180,178,169,0.18)':'rgba(95,94,90,0.18)';
    const GRID_C=isDark?'rgba(180,178,169,0.07)':'rgba(95,94,90,0.07)';
    const LABEL_C='#94a3b8';

    ctx.clearRect(0,0,W,H); ctx.fillStyle='#0d1117'; ctx.fillRect(0,0,W,H);

    const ce=(x1,y1,z1,x2,y2,z2,col,lw,dash)=>{
      const a=proj(x1,y1,z1),b=proj(x2,y2,z2);
      ctx.beginPath();ctx.setLineDash(dash||[]);
      ctx.strokeStyle=col;ctx.lineWidth=lw;
      ctx.moveTo(a.sx,a.sy);ctx.lineTo(b.sx,b.sy);ctx.stroke();ctx.setLineDash([]);
    };
    const edge=(x1,y1,z1,x2,y2,z2)=>ce(x1,y1,z1,x2,y2,z2,CUBE_C,1);
    const grid=(x1,y1,z1,x2,y2,z2)=>ce(x1,y1,z1,x2,y2,z2,GRID_C,0.5,[3,5]);
    edge(0,0,0,1,0,0);edge(0,0,0,0,1,0);edge(0,0,0,0,0,1);
    edge(1,0,0,1,1,0);edge(1,0,0,1,0,1);edge(0,1,0,1,1,0);edge(0,1,0,0,1,1);
    edge(0,0,1,1,0,1);edge(0,0,1,0,1,1);edge(1,1,0,1,1,1);edge(1,0,1,1,1,1);edge(0,1,1,1,1,1);
    [0.25,0.5,0.75].forEach(v=>{
      grid(v,0,0,v,1,0);grid(v,0,0,v,0,1);
      grid(0,v,0,1,v,0);grid(0,v,0,0,v,1);
      grid(0,0,v,1,0,v);grid(0,0,v,0,1,v);
    });

    const axLine=(x1,y1,z1,x2,y2,z2,col,label)=>{
      const a=proj(x1,y1,z1),b=proj(x2,y2,z2);
      ctx.beginPath();ctx.strokeStyle=col+'aa';ctx.lineWidth=2;
      ctx.moveTo(a.sx,a.sy);ctx.lineTo(b.sx,b.sy);ctx.stroke();
      ctx.fillStyle=col+'cc';ctx.font='500 12px sans-serif';ctx.textAlign='center';
      ctx.fillText(label,b.sx+(b.sx-a.sx)*0.14,b.sy+(b.sy-a.sy)*0.14+4);
    };
    axLine(0,0,0,1.2,0,0,'#E24B4A','Dist →');
    axLine(0,0,0,0,1.2,0,'#1D9E75','Cost →');
    axLine(0,0,0,0,0,1.2,'#BA7517','Time →');

    if(!solutions||!solutions.length){
      ctx.fillStyle='rgba(148,163,184,0.35)';ctx.font='13px sans-serif';ctx.textAlign='center';
      ctx.fillText('Run the solver to plot solutions in 3D',W/2,H/2+30);
      return;
    }

    const ds=solutions.map(s=>s.scores.dist),cs=solutions.map(s=>s.scores.cost),ts=solutions.map(s=>s.scores.time);
    const[minD,maxD]=[Math.min(...ds),Math.max(...ds)];
    const[minC,maxC]=[Math.min(...cs),Math.max(...cs)];
    const[minT,maxT]=[Math.min(...ts),Math.max(...ts)];
    const solMD=solutions.reduce((a,b)=>a.scores.dist<b.scores.dist?a:b);
    const solMC=solutions.reduce((a,b)=>a.scores.cost<b.scores.cost?a:b);
    const solMT=solutions.reduce((a,b)=>a.scores.time<b.scores.time?a:b);

    ctx.font='10px sans-serif';ctx.fillStyle=LABEL_C;
    [0.5,1].forEach(t=>{
      const pd=proj(t,0,0),pc=proj(0,t,0),pt=proj(0,0,t);
      ctx.textAlign='center';
      ctx.fillText(Math.round(minD+(maxD-minD)*t),pd.sx,pd.sy+14);
      ctx.fillText('$'+Math.round(minC+(maxC-minC)*t),pc.sx-18,pc.sy+4);
      ctx.fillText(Math.round(minT+(maxT-minT)*t)+'m',pt.sx,pt.sy+14);
    });

    const pts=solutions.map((sol,idx)=>{
      const p=proj(norm(sol.scores.dist,minD,maxD),norm(sol.scores.cost,minC,maxC),norm(sol.scores.time,minT,maxT));
      const isSpecial=[solMD,solMC,solMT].includes(sol);
      let color='#378ADD';
      if(sol===solMD)color='#E24B4A';
      else if(sol===solMC)color='#1D9E75';
      else if(sol===solMT)color='#BA7517';
      return{...p,sol,color,isSpecial,r:isSpecial?8:5.5,idx};
    });
    pts.sort((a,b)=>b.z3-a.z3);
    projRef.current=pts;

    pts.forEach(p=>{
      const floor=proj(norm(p.sol.scores.dist,minD,maxD),0,norm(p.sol.scores.time,minT,maxT));
      ctx.beginPath();ctx.setLineDash([3,4]);
      ctx.strokeStyle=p.color+'40';ctx.lineWidth=0.8;
      ctx.moveTo(p.sx,p.sy);ctx.lineTo(floor.sx,floor.sy);ctx.stroke();ctx.setLineDash([]);
    });

    pts.forEach(p=>{
      const isHov=stateRef.current.hoveredIdx===p.idx;
      if(p.isSpecial||isHov){
        ctx.beginPath();ctx.arc(p.sx,p.sy,p.r+5,0,Math.PI*2);
        ctx.fillStyle=p.color+'28';ctx.fill();
      }
      ctx.beginPath();ctx.arc(p.sx,p.sy,isHov?p.r+2:p.r,0,Math.PI*2);
      ctx.fillStyle=p.color;ctx.fill();
      if(p.isSpecial){
        ctx.beginPath();ctx.arc(p.sx,p.sy,p.r+2,0,Math.PI*2);
        ctx.strokeStyle=p.color;ctx.lineWidth=1.5;ctx.stroke();
      }
    });
  },[solutions,project]);

  useEffect(()=>{draw();},[solutions,draw]);
  useEffect(()=>{const ro=new ResizeObserver(draw);if(wrapRef.current)ro.observe(wrapRef.current);return()=>ro.disconnect();},[draw]);

  const onMouseDown=e=>{stateRef.current.dragging=true;stateRef.current.lx=e.clientX;stateRef.current.ly=e.clientY;};
  const onMouseUp=()=>stateRef.current.dragging=false;
  const onWheel=e=>{stateRef.current.zoom=Math.max(0.5,Math.min(2.8,stateRef.current.zoom-e.deltaY*0.001));draw();e.preventDefault();};
  const onMouseMove=e=>{
    const s=stateRef.current;
    if(s.dragging){
      s.rotY+=(e.clientX-s.lx)*0.012;
      s.rotX=Math.max(-1.4,Math.min(1.4,s.rotX+(e.clientY-s.ly)*0.010));
      s.lx=e.clientX;s.ly=e.clientY;draw();return;
    }
    const rect=wrapRef.current.getBoundingClientRect();
    const mx=e.clientX-rect.left,my=e.clientY-rect.top;
    let hit=-1;
    for(const p of [...projRef.current].reverse()){if(Math.hypot(mx-p.sx,my-p.sy)<p.r+5){hit=p.idx;break;}}
    if(hit!==s.hoveredIdx){s.hoveredIdx=hit;draw();}
    if(tipRef.current){
      if(hit>=0&&solutions[hit]){
        const sol=solutions[hit];
        tipRef.current.style.display='block';
        tipRef.current.style.left=Math.min(mx+14,wrapRef.current.clientWidth-170)+'px';
        tipRef.current.style.top=Math.max(my-70,6)+'px';
        tipRef.current.innerHTML=`<b>${sol.route.join(' → ')}</b>Dist: ${sol.scores.dist}<br>Cost: $${sol.scores.cost}<br>Time: ${sol.scores.time}m`;
      } else tipRef.current.style.display='none';
    }
  };
  const onMouseLeave=()=>{stateRef.current.dragging=false;stateRef.current.hoveredIdx=-1;draw();if(tipRef.current)tipRef.current.style.display='none';};

  const extremes=useMemo(()=>{
    if(!solutions?.length) return null;
    return{
      minDist:solutions.reduce((a,b)=>a.scores.dist<b.scores.dist?a:b),
      minCost:solutions.reduce((a,b)=>a.scores.cost<b.scores.cost?a:b),
      minTime:solutions.reduce((a,b)=>a.scores.time<b.scores.time?a:b),
    };
  },[solutions]);

  return(
    <div className="card pareto3d-card">
      <div className="p3d-header">
        <h3><Box size={18}/>3D Pareto front</h3>
        <div className="p3d-legend">
          <span><span className="p3d-dot" style={{background:'#378ADD'}}/>All</span>
          <span><span className="p3d-dot" style={{background:'#E24B4A'}}/>Min dist</span>
          <span><span className="p3d-dot" style={{background:'#1D9E75'}}/>Min cost</span>
          <span><span className="p3d-dot" style={{background:'#BA7517'}}/>Min time</span>
        </div>
      </div>
      {extremes&&(
        <div className="p3d-metrics">
          <div className="p3d-metric"><div className="p3d-ml">Solutions</div><div className="p3d-mv">{solutions.length}</div></div>
          <div className="p3d-metric"><div className="p3d-ml">Best dist</div><div className="p3d-mv" style={{color:'#E24B4A'}}>{extremes.minDist.scores.dist}</div></div>
          <div className="p3d-metric"><div className="p3d-ml">Best cost</div><div className="p3d-mv" style={{color:'#1D9E75'}}>${extremes.minCost.scores.cost}</div></div>
          <div className="p3d-metric"><div className="p3d-ml">Best time</div><div className="p3d-mv" style={{color:'#BA7517'}}>{extremes.minTime.scores.time}m</div></div>
        </div>
      )}
      <div ref={wrapRef} className="p3d-canvas-wrap"
        onMouseDown={onMouseDown} onMouseUp={onMouseUp}
        onMouseMove={onMouseMove} onMouseLeave={onMouseLeave}
        onWheel={onWheel} style={{cursor:'grab'}}>
        <canvas ref={canvasRef} style={{width:'100%',height:'100%'}}/>
        {(!solutions||!solutions.length)&&(
          <div className="p3d-empty">
            <svg width="44" height="44" viewBox="0 0 44 44" fill="none" style={{opacity:0.25}}>
              <path d="M22 4L40 14V30L22 40L4 30V14L22 4Z" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M22 4L22 40M4 14L40 14M4 30L40 30" stroke="currentColor" strokeWidth="0.75" strokeDasharray="3 3"/>
            </svg>
            Run the solver to plot solutions in 3D
          </div>
        )}
        <div ref={tipRef} className="p3d-tip"/>
      </div>
      {solutions?.length>0&&(
        <div className="p3d-axis-bar">
          <span style={{color:'#E24B4A'}}>X = Distance</span>
          <span style={{color:'#1D9E75'}}>Y = Cost</span>
          <span style={{color:'#BA7517'}}>Z = Time</span>
          <span style={{marginLeft:'auto',color:'var(--text-muted)'}}>Drag · Scroll</span>
        </div>
      )}
    </div>
  );
};

// ─── Benchmark Gap Card ────────────────────────────────────────────────────────
const BenchmarkCard = ({ benchmark }) => {
  if (!benchmark) return null;
  const { known_optimal_dist, solver_best_dist, gap_percent } = benchmark;
  const isGood = gap_percent <= 5;
  const isOk   = gap_percent <= 15;
  const color   = isGood ? '#1D9E75' : isOk ? '#BA7517' : '#E24B4A';
  return (
    <div className="card benchmark-card">
      <h3><Award size={18}/>TSPLIB benchmark result</h3>
      <div className="benchmark-grid">
        <div className="bm-stat"><div className="bm-label">Known optimal</div><div className="bm-val">{known_optimal_dist}</div></div>
        <div className="bm-stat"><div className="bm-label">Solver best</div><div className="bm-val">{solver_best_dist}</div></div>
        <div className="bm-stat"><div className="bm-label">Gap</div><div className="bm-val" style={{color}}>{gap_percent > 0 ? '+' : ''}{gap_percent}%</div></div>
      </div>
      <div className="bm-bar-wrap">
        <div className="bm-bar" style={{width:`${Math.min(100, 100 - gap_percent*2)}%`, background:color}}/>
      </div>
      <div className="bm-note">
        {isGood ? 'Excellent — solver is within 5% of optimal.' : isOk ? 'Good — within 15% of optimal. Try more iterations.' : 'Far from optimal — increase swarm size or iterations.'}
      </div>
    </div>
  );
};

// ─── Main App ─────────────────────────────────────────────────────────────────
function App() {
  const [graphData,      setGraphData]      = useState({ nodes:[], edges:[], source:'default', has_coords:false });
  const [solutions,      setSolutions]      = useState([]);
  const [loading,        setLoading]        = useState(false);
  const [selectedRoute,  setSelectedRoute]  = useState(null);
  const [benchmark,      setBenchmark]      = useState(null);
  const [tspStatus,      setTspStatus]      = useState(null);  // {msg, type}
  const [params,         setParams]         = useState({ pop_size:50, max_iter:100, start_node:'A' });

  const fetchGraph = useCallback(() => {
    axios.get(`${API_BASE}/graph/structure`)
      .then(res => setGraphData(res.data))
      .catch(err => console.error('Graph fetch error:', err));
  }, []);

  useEffect(() => { fetchGraph(); }, [fetchGraph]);

  const runSolver = async () => {
    setLoading(true); setSelectedRoute(null); setBenchmark(null);
    try {
      const res = await axios.post(`${API_BASE}/solve/apso`, params);
      setSolutions(res.data.solutions);
      if (res.data.benchmark) setBenchmark(res.data.benchmark);
    } catch { alert('Solver failed. Is the backend running?'); }
    finally { setLoading(false); }
  };

  const handleTspUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setTspStatus({ msg: `Loading ${file.name}…`, type: 'loading' });
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await axios.post(`${API_BASE}/graph/load-tsplib`, form, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setTspStatus({ msg: `Loaded ${res.data.filename} — ${res.data.node_count} nodes${res.data.known_optimal ? ' · optimal known' : ''}`, type: 'success' });
      setSolutions([]); setSelectedRoute(null); setBenchmark(null);
      // Set start_node to first node in loaded instance
      if (res.data.nodes_preview?.length) setParams(p => ({ ...p, start_node: res.data.nodes_preview[0] }));
      fetchGraph();
    } catch (err) {
      setTspStatus({ msg: err.response?.data?.detail || 'Upload failed', type: 'error' });
    }
    e.target.value = '';
  };

  const handleReset = async () => {
    await axios.post(`${API_BASE}/graph/reset`);
    setSolutions([]); setSelectedRoute(null); setBenchmark(null);
    setTspStatus(null);
    setParams(p => ({ ...p, start_node: 'A' }));
    fetchGraph();
  };

  const extremes = useMemo(() => {
    if (!solutions.length) return null;
    return {
      minDist: solutions.reduce((a,b) => a.scores.dist < b.scores.dist ? a : b),
      minCost: solutions.reduce((a,b) => a.scores.cost < b.scores.cost ? a : b),
      minTime: solutions.reduce((a,b) => a.scores.time < b.scores.time ? a : b),
    };
  }, [solutions]);

  const isTsplib = graphData.source !== 'default';

  return (
    <div className="app-container">
      <header className="top-nav">
        <div className="brand">
          <Activity size={26} className="text-blue"/>
          <h1>MultiObjective TSP Solver</h1>
          {isTsplib && <span className="tsp-badge">TSPLIB: {graphData.source}</span>}
        </div>
        <div className="nav-actions">
          <label className="upload-btn" title="Upload a .tsp file">
            <Upload size={15}/> Load TSPLIB
            <input type="file" accept=".tsp" onChange={handleTspUpload} style={{display:'none'}}/>
          </label>
          {isTsplib && (
            <button className="reset-btn" onClick={handleReset} title="Restore default 8-node graph">
              <RotateCcw size={14}/> Reset
            </button>
          )}
        </div>
      </header>

      {tspStatus && (
        <div className={`tsp-status tsp-status--${tspStatus.type}`}>{tspStatus.msg}</div>
      )}

      <main className="dashboard">
        <aside className="left-panel">
          <section className="card">
            <h3><Play size={18}/>Optimization parameters</h3>
            <div className="input-grid">
              <div className="input-group"><label>Swarm size</label>
                <input type="number" value={params.pop_size} onChange={e=>setParams({...params,pop_size:+e.target.value})}/>
              </div>
              <div className="input-group"><label>Generations</label>
                <input type="number" value={params.max_iter} onChange={e=>setParams({...params,max_iter:+e.target.value})}/>
              </div>
              <div className="input-group"><label>Start node</label>
                <input type="text" value={params.start_node} onChange={e=>setParams({...params,start_node:e.target.value.toUpperCase()})}/>
              </div>
            </div>
            <div className="graph-meta">
              <span>{graphData.node_count||0} nodes · {graphData.edge_count||0} edges</span>
              {graphData.known_optimal && <span className="opt-tag">Optimal known</span>}
            </div>
            <button className="run-btn" onClick={runSolver} disabled={loading}>
              {loading ? <span className="pulse">Optimizing…</span> : 'Launch Solver'}
            </button>
          </section>

          {solutions.length > 0 && extremes && (
            <>
              <section className="card">
                <h3>Best trade-offs</h3>
                <div className="action-buttons">
                  <button onClick={()=>setSelectedRoute(extremes.minDist.route)} className={`insight-btn${selectedRoute===extremes.minDist.route?' active':''}`}>
                    <Route size={15}/>Min distance <span>({extremes.minDist.scores.dist})</span>
                  </button>
                  <button onClick={()=>setSelectedRoute(extremes.minCost.route)} className={`insight-btn${selectedRoute===extremes.minCost.route?' active':''}`}>
                    <TrendingDown size={15}/>Min cost <span>(${extremes.minCost.scores.cost})</span>
                  </button>
                  <button onClick={()=>setSelectedRoute(extremes.minTime.route)} className={`insight-btn${selectedRoute===extremes.minTime.route?' active':''}`}>
                    <Clock size={15}/>Min time <span>({extremes.minTime.scores.time}m)</span>
                  </button>
                </div>
              </section>

              <section className="card pareto-list-card">
                <h3><List size={18}/>Pareto front ({solutions.length})</h3>
                <div className="scrollable-list">
                  {solutions.map((sol,i) => (
                    <div key={i} className={`solution-item${selectedRoute===sol.route?' selected':''}`} onClick={()=>setSelectedRoute(sol.route)}>
                      <div className="route-path">{sol.route.join(' → ')}</div>
                      <div className="route-stats">
                        <span className="stat dist">D: {sol.scores.dist}</span>
                        <span className="stat cost">C: ${sol.scores.cost}</span>
                        <span className="stat time">T: {sol.scores.time}m</span>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </>
          )}
        </aside>

        <section className="right-panel">
          <div className="card graph-card">
            <div className="graph-header">
              <h3><MapIcon size={18}/>Network topology</h3>
              <div className="status-badges">
                <div className="badge start-badge">Start: {params.start_node}</div>
                {!isTsplib && (
                  <div className="ng-edge-legend">
                    <span className="ng-etype highway">Highway</span>
                    <span className="ng-etype local">Local</span>
                    <span className="ng-etype scenic">Scenic</span>
                  </div>
                )}
                {selectedRoute
                  ? <div className="badge active">Route shown</div>
                  : <div className="badge neutral">Select a route</div>}
              </div>
            </div>
            <NetworkGraph graphData={graphData} selectedRoute={selectedRoute} startNode={params.start_node}/>
            <div className="ng-hint">
              {isTsplib
                ? `TSPLIB instance · ${graphData.node_count} cities · hover edges for weights`
                : 'Hover edges for weight details · 8-node custom graph'}
            </div>
          </div>

          {benchmark && <BenchmarkCard benchmark={benchmark}/>}
          <ParetoChart3D solutions={solutions}/>
        </section>
      </main>
    </div>
  );
}

export default App;