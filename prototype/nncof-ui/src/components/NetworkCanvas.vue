<script setup lang="ts">
import { onMounted, ref, watch, onUnmounted, computed } from 'vue';
import { Save, Clock6, Scan } from 'lucide-vue-next';
import * as d3 from 'd3';

import { useNetworkStore } from '../store/network';
import type { Message, NetworkNode, Subscription, NodeEdge, NodeSize } from '../types';

const store = useNetworkStore();
const svgRef = ref<SVGSVGElement | null>(null);

// src/assets/ 내 이미지를 Vite가 해시 처리한 URL로 매핑
const assetImages = import.meta.glob('../assets/*.{png,jpg,jpeg,svg,gif,webp}', {
  eager: true,
  import: 'default',
}) as Record<string, string>;
const getNodeImageUrl = (filename: string): string => {
  const key = `../assets/${filename}`;
  return assetImages[key] || '';
};
let svg: d3.Selection<SVGSVGElement, unknown, null, undefined>;
let mainGroup: d3.Selection<SVGGElement, unknown, null, undefined>;
let nodesGroup: d3.Selection<SVGGElement, unknown, null, undefined>;
let linksGroup: d3.Selection<SVGGElement, unknown, null, undefined>;
let topologyGroup: d3.Selection<SVGGElement, unknown, null, undefined>;
let signalsGroup: d3.Selection<SVGGElement, unknown, null, undefined>;
let zoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown>;
let containerWidth = 0;
let containerHeight = 0;

onMounted(() => {
  if (!svgRef.value) return;
  initNetwork();
  render();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
});

const handleResize = () => {
  if (!svgRef.value || containerWidth === 0 || containerHeight === 0) return;
  const rect = svgRef.value!.getBoundingClientRect();
  const newWidth = rect.width;
  const newHeight = rect.height;

  const transform = d3.zoomTransform(svgRef.value!);
  const dx = (newWidth - containerWidth) / 2;
  const dy = (newHeight - containerHeight) / 2;

  containerWidth = newWidth;
  containerHeight = newHeight;

  const newTransform = d3.zoomIdentity
    .translate(transform.x + dx, transform.y + dy)
    .scale(transform.k);

  svg.call(zoomBehavior.transform, newTransform);
};

const initNetwork = () => {
  svg = d3.select(svgRef.value!);
  mainGroup = svg.append('g').attr('class', 'main-group');
  topologyGroup = mainGroup.append('g').attr('class', 'topology-group');
  linksGroup = mainGroup.append('g').attr('class', 'links-group');
  nodesGroup = mainGroup.append('g').attr('class', 'nodes-group');
  signalsGroup = mainGroup.append('g').attr('class', 'signals-group');

  const { width, height } = svgRef.value!.getBoundingClientRect();
  containerWidth = width;
  containerHeight = height;
  mainGroup.attr('transform', `translate(${width / 2}, ${height / 2})`);

  zoomBehavior = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => {
      mainGroup.attr('transform', event.transform);
    });

  svg.call(zoomBehavior);
  svg.call(zoomBehavior.transform, d3.zoomIdentity.translate(width / 2, height / 2));

  // Arrow markers — refX=10으로 화살표 끝(viewBox x=10)을 경로 끝(노드 가장자리)에 정렬
  svg.append('defs').append('marker')
    .attr('id', 'arrowhead')
    .attr('viewBox', '0 0 10 10')
    .attr('refX', 10)
    .attr('refY', 5)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto-start-reverse')
    .append('path')
    .attr('d', 'M 0 0 L 10 5 L 0 10 z')
    .attr('fill', '#60a5fa');

  svg.select('defs').append('marker')
    .attr('id', 'arrowhead-cyan')
    .attr('viewBox', '0 0 10 10')
    .attr('refX', 10)
    .attr('refY', 5)
    .attr('markerWidth', 8)
    .attr('markerHeight', 8)
    .attr('orient', 'auto-start-reverse')
    .append('path')
    .attr('d', 'M 0 0 L 10 5 L 0 10 z')
    .attr('fill', '#22d3ee');

  // 이미지 노드용 clipPath (large/normal/small 크기별)
  const sizes: NodeSize[] = ['large', 'normal', 'small'];
  sizes.forEach((size) => {
    const dim = getNodeDimensions(size);
    svg.select('defs').append('clipPath')
      .attr('id', `clip-${size}`)
      .append('rect')
      .attr('width', dim.w)
      .attr('height', dim.h)
      .attr('x', -dim.w / 2)
      .attr('y', -dim.h / 2)
      .attr('rx', dim.rx);
  });
};

const render = () => {
  renderNodeEdges();
  renderNodes();
  renderLinks();
};

const renderNodes = () => {
  const nodeSelection = nodesGroup.selectAll<SVGGElement, NetworkNode>('.node-group')
    .data(store.nodes, (d) => d.id);

  const nodeEnter = nodeSelection.enter()
    .append('g')
    .attr('class', 'node-group cursor-grab active:cursor-grabbing')
    .on('click', (_event, d: NetworkNode) => {
      store.selectedNodeId = d.id;
    })
    .on('dblclick', (_event, d: NetworkNode) => {
      store.selectedNodeId = d.id;
    })
    .on('contextmenu', (event, d: NetworkNode) => {
      event.preventDefault();
      store.selectedNodeId = d.id;
    })
    .call(d3.drag<SVGGElement, NetworkNode>()
      .on('drag', function (event, d: NetworkNode) {
        d.x += event.dx;
        d.y += event.dy;
        d3.select(this).attr('transform', `translate(${d.x}, ${d.y})`);
        renderNodeEdges();
        renderLinks();
      }));

  nodeEnter.append('rect')
    .attr('width', (d: NetworkNode) => getNodeDimensions(d.size).w)
    .attr('height', (d: NetworkNode) => getNodeDimensions(d.size).h)
    .attr('x', (d: NetworkNode) => -getNodeDimensions(d.size).w / 2)
    .attr('y', (d: NetworkNode) => -getNodeDimensions(d.size).h / 2)
    .attr('rx', (d: NetworkNode) => getNodeDimensions(d.size).rx)
    .attr('class', 'stroke-2')
    .attr('fill', (d) => d.image ? 'none' : '#1e293b')
    .attr('stroke', (d) => d.image ? 'none' : getNodeColor(d.type));

  nodeEnter.append('text')
    .attr('dy', (d: NetworkNode) => getNodeDimensions(d.size).textDy)
    .attr('text-anchor', 'middle')
    .attr('class', 'text-[10px] font-bold fill-slate-400 select-none')
    .text((d) => d.name);

  nodeEnter.append('circle').attr('r', (d: NetworkNode) => getNodeDimensions(d.size).glowR).attr('fill', (d) => getNodeColor(d.type)).attr('class', 'opacity-30').attr('filter', 'blur(4px)');
  nodeEnter.append('circle').attr('r', (d: NetworkNode) => getNodeDimensions(d.size).dotR).attr('fill', 'white').attr('class', 'opacity-20');

  // image 속성이 있는 노드는 rounded rect 클리핑된 이미지 표시
  nodeEnter.filter((d: NetworkNode) => !!d.image)
    .append('image')
    .attr('x', (d: NetworkNode) => -getNodeDimensions(d.size).w / 2)
    .attr('y', (d: NetworkNode) => -getNodeDimensions(d.size).h / 2)
    .attr('width', (d: NetworkNode) => getNodeDimensions(d.size).w)
    .attr('height', (d: NetworkNode) => getNodeDimensions(d.size).h)
    .attr('preserveAspectRatio', 'xMidYMid slice')
    .attr('clip-path', (d: NetworkNode) => `url(#clip-${d.size || 'normal'})`)
    .attr('href', (d: NetworkNode) => getNodeImageUrl(d.image!));

  // AI Analyzer Ring (only for NCOF)
  const analyzer = nodeEnter.filter(d => d.type === 'NCOF')
    .append('g')
    .attr('class', 'analyzer-group')
    .style('opacity', 0);

  analyzer.append('circle')
    .attr('r', (d: NetworkNode) => getNodeDimensions(d.size).w * 0.82)
    .attr('fill', 'none')
    .attr('stroke', '#60a5fa')
    .attr('stroke-width', 2)
    .attr('stroke-dasharray', '4,4')
    .attr('class', 'analyzer-ring');

  analyzer.append('circle')
    .attr('r', (d: NetworkNode) => getNodeDimensions(d.size).w * 0.82)
    .attr('fill', 'none')
    .attr('stroke', '#3b82f6')
    .attr('stroke-width', 1)
    .attr('stroke-dasharray', '2,8')
    .attr('class', 'analyzer-ring-outer');

  // analyzer.append('text')
  //   .attr('dy', (d: NetworkNode) => -(getNodeDimensions(d.size).w * 2.74))
  //   .attr('text-anchor', 'middle')
  //   .attr('class', 'text-[8px] font-black fill-blue-400 uppercase tracking-widest animate-pulse')
  //   .text('AI Analyzing...');

  // 말풍선 — NCOF 오른쪽 상단에 코딩 텍스트 스크롤 효과
  const bubble = analyzer.append('g')
    .attr('class', 'speech-bubble')
    .attr('transform', 'translate(0, -85)');

  bubble.append('rect')
    .attr('x', -85)
    .attr('y', -25)
    .attr('width', 170)
    .attr('height', 50)
    .attr('rx', 10)
    .attr('fill', '#0f172a')
    .attr('stroke', '#3b82f6')
    .attr('stroke-width', 1)
    .attr('opacity', 0.95);

  bubble.append('polygon')
    .attr('points', '-6,25 0,34 6,25')
    .attr('fill', '#0f172a')
    .attr('stroke', '#3b82f6')
    .attr('stroke-width', 1);

  bubble.append('foreignObject')
    .attr('x', -78)
    .attr('y', -22)
    .attr('width', 156)
    .attr('height', 44)
    .html(`
      <div xmlns="http://www.w3.org/1999/xhtml" style="overflow:hidden;height:100%;width:100%;font-family:'Courier New',monospace;font-size:9px;color:#60a5fa;line-height:1.6;background:transparent;">
        <div class="bubble-scroll-inner" style="padding:1px 0;">
          &gt; ncof --analyze<br/>
          &gt; forwarding to newral network<br/>
          &gt; awaiting callback...<br/>
          &gt; analysis ready
        </div>
      </div>
    `);

  nodeSelection.merge(nodeEnter as any).attr('transform', (d: NetworkNode) => `translate(${d.x}, ${d.y})`);
};

const renderNodeEdges = () => {
  const edges = topologyGroup.selectAll<SVGLineElement, NodeEdge>('.topology-edge')
    .data(store.nodeEdges, (d: NodeEdge) => d.id);

  const edgeEnter = edges.enter()
    .append('line')
    .attr('class', 'topology-edge');

  edgeEnter.merge(edges as any)
    .attr('x1', (d: NodeEdge) => {
      const source = store.nodes.find(n => n.id === d.from);
      return source ? source.x : 0;
    })
    .attr('y1', (d: NodeEdge) => {
      const source = store.nodes.find(n => n.id === d.from);
      return source ? source.y : 0;
    })
    .attr('x2', (d: NodeEdge) => {
      const target = store.nodes.find(n => n.id === d.to);
      return target ? target.x : 0;
    })
    .attr('y2', (d: NodeEdge) => {
      const target = store.nodes.find(n => n.id === d.to);
      return target ? target.y : 0;
    });

  edges.exit().remove();

  // Edge labels (interface names like N13, N7, etc.)
  const labeledEdges = store.nodeEdges.filter((d: NodeEdge) => d.label);
  const labels = topologyGroup.selectAll<SVGTextElement, NodeEdge>('.topology-edge-label')
    .data(labeledEdges, (d: NodeEdge) => d.id);

  const labelEnter = labels.enter()
    .append('text')
    .attr('class', 'topology-edge-label');

  labelEnter.merge(labels as any)
    .attr('text-anchor', 'middle')
    .attr('dy', -8)
    .text((d: NodeEdge) => d.label!)
    .attr('x', (d: NodeEdge) => {
      const source = store.nodes.find(n => n.id === d.from);
      const target = store.nodes.find(n => n.id === d.to);
      if (!source || !target) return 0;
      return (source.x + target.x) / 2;
    })
    .attr('y', (d: NodeEdge) => {
      const source = store.nodes.find(n => n.id === d.from);
      const target = store.nodes.find(n => n.id === d.to);
      if (!source || !target) return 0;
      return (source.y + target.y) / 2;
    });

  labels.exit().remove();
};

// (from, to) 그룹 내 index 기반 수직 오프셋 계산 (최대 5개)
const getLinkOffset = (from: string, to: string, id: string, gap: number = 8) => {
  const sameGroup = store.activeSubscriptions
    .filter(s => s.from === from && s.to === to)
    .slice(0, 5);
  const index = sameGroup.findIndex(s => s.id === id);
  if (index === -1) return 0;
  const count = sameGroup.length;
  return (index - (count - 1) / 2) * gap;
};

// 오프셋이 적용된 링크 끝점 반환
const getOffsetEndpoints = (d: Subscription) => {
  const source = store.nodes.find(n => n.id === d.from);
  const target = store.nodes.find(n => n.id === d.to);
  if (!source || !target) return null;
  const { sx, sy, tx, ty } = adjustLinkEndpoints(source, target);
  const dx = tx - sx;
  const dy = ty - sy;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;
  const nx = -dy / dist;
  const ny = dx / dist;
  const offset = getLinkOffset(d.from, d.to, d.id);
  return { x1: sx + nx * offset, y1: sy + ny * offset, x2: tx + nx * offset, y2: ty + ny * offset };
};

const isNcofLink = (d: { from: string; type?: string }) =>
  (d.from === 'NCOF' || d.from === 'NEF') && d.type === 'NOTIFICATION';

const renderLinks = () => {
  const links = linksGroup.selectAll<SVGLineElement, Subscription>('.link-line')
    .data(store.activeSubscriptions, (d) => d.id);

  links.enter()
    .append('line')
    .merge(links as any)
    .attr('class', (d: Subscription) => isNcofLink(d)
      ? 'link-line stroke-cyan-400 flowing-line'
      : 'link-line stroke-blue-500/60 flowing-line')
    .attr('stroke-width', (d: Subscription) => isNcofLink(d) ? 4 : 2)
    .attr('marker-end', (d: Subscription) => isNcofLink(d)
      ? 'url(#arrowhead-cyan)'
      : 'url(#arrowhead)')
    .attr('x1', (d: Subscription) => getOffsetEndpoints(d)?.x1 ?? 0)
    .attr('y1', (d: Subscription) => getOffsetEndpoints(d)?.y1 ?? 0)
    .attr('x2', (d: Subscription) => getOffsetEndpoints(d)?.x2 ?? 0)
    .attr('y2', (d: Subscription) => getOffsetEndpoints(d)?.y2 ?? 0);

  links.exit().remove();

  // (from, to) 그룹별로 하나의 label만 표시, 개수 표시
  const linkGroupMap = new Map<string, { from: string; to: string; count: number }>();
  store.activeSubscriptions.forEach((s) => {
    const key = `${s.from}:${s.to}`;
    const group = linkGroupMap.get(key);
    if (group) {
      group.count++;
    } else {
      linkGroupMap.set(key, { from: s.from, to: s.to, count: 1 });
    }
  });
  const linkGroups = Array.from(linkGroupMap.values());

  const labels = linksGroup.selectAll<SVGTextElement, { from: string; to: string; count: number }>('.link-label')
    .data(linkGroups, (d: any) => `${d.from}:${d.to}`);

  labels.enter()
    .append('text')
    .attr('class', (d: { from: string }) => isNcofLink(d)
      ? 'link-label text-[9px] fill-cyan-400 font-bold select-none'
      : 'link-label text-[9px] fill-blue-300 font-bold select-none')
    .attr('text-anchor', 'middle')
    .merge(labels as any)
    .text((d) => d.count > 1 ? `SUBSCRIBED (${d.count})` : 'SUBSCRIBED')
    .attr('transform', (d) => {
      const source = store.nodes.find(n => n.id === d.from);
      const target = store.nodes.find(n => n.id === d.to);
      if (!source || !target) return '';

      const { sx, sy, tx, ty } = adjustLinkEndpoints(source, target);
      const midX = (sx + tx) / 2;
      const midY = (sy + ty) / 2;
      const dx = tx - sx;
      const dy = ty - sy;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const nx = -dy / dist;
      const ny = dx / dist;

      // 다중 링크 그룹의 중앙(offset=0) 위치에 라벨 배치
      const groupCount = Math.min(
        store.activeSubscriptions.filter(s => s.from === d.from && s.to === d.to).length,
        5
      );
      const labelOffset = 12 + ((groupCount - 1) / 2) * 8;

      return `translate(${midX + nx * labelOffset}, ${midY + ny * labelOffset})`;
    });

  labels.exit().remove();
};

// 중심점에서 사각형 가장자리까지의 교차점 계산 (사각형은 center 기준 ±w/2, ±h/2)
const getRectEdgePoint = (
  cx: number, cy: number,
  dx: number, dy: number,
  halfW: number, halfH: number,
) => {
  // (cx, cy)에서 (cx+dx, cy+dy) 방향으로 사각형 경계와 만나는 점
  const absDx = Math.abs(dx);
  const absDy = Math.abs(dy);
  if (absDx === 0 && absDy === 0) return { x: cx, y: cy };

  if (absDx === 0) {
    // 수직 이동
    const t = halfH / absDy;
    return { x: cx, y: cy + t * dy };
  }
  if (absDy === 0) {
    // 수평 이동
    const t = halfW / absDx;
    return { x: cx + t * dx, y: cy };
  }

  const t = Math.min(halfW / absDx, halfH / absDy);
  return { x: cx + t * dx, y: cy + t * dy };
};

// 소스/타겟 노드의 사각형 가장자리에서 시작하고 끝나도록 링크 경로 조정
const adjustLinkEndpoints = (source: NetworkNode, target: NetworkNode) => {
  const sDim = getNodeDimensions(source.size);
  const tDim = getNodeDimensions(target.size);

  const vx = target.x - source.x;
  const vy = target.y - source.y;

  const srcEdge = getRectEdgePoint(source.x, source.y, vx, vy, sDim.w / 2, sDim.h / 2);
  const tgtEdge = getRectEdgePoint(target.x, target.y, -vx, -vy, tDim.w / 2, tDim.h / 2);

  return { sx: srcEdge.x, sy: srcEdge.y, tx: tgtEdge.x, ty: tgtEdge.y };
};

const calculatePath = (source: NetworkNode, target: NetworkNode) => {
  const { sx, sy, tx, ty } = adjustLinkEndpoints(source, target);
  return `M${sx},${sy}L${tx},${ty}`;
};

const getNodeColor = (type: NetworkNode['type']) => {
  switch (type) {
    case 'NCOF': return '#e0e391';
    case 'RICF': return '#10b981';
    case 'AF': return '#f59e0b';
    case 'AMF': return '#71910b';
    case 'PCF': return '#4ed4cf';
    case 'SMF': return '#b572d6';
    case 'UE': return '#3b82f6';
    case 'UPF': return '#b572d6';
    // case 'WIFI': return '#335182';
    // case 'GNODEB': return '#756853';
    default: return '#64748b';
  }
};

const getNodeDimensions = (size?: NodeSize) => {
  switch (size) {
    case 'large': return { w: 84, h: 84, rx: 16, glowR: 16, dotR: 8, textDy: 30 };
    case 'small': return { w: 44, h: 44, rx: 8, glowR: 6, dotR: 3, textDy: 18 };
    default: return { w: 64, h: 64, rx: 12, glowR: 12, dotR: 6, textDy: 24 };
  }
};

const animateMessage = async (msg: Message) => {
  const source = store.nodes.find(n => n.id === msg.from);
  const target = store.nodes.find(n => n.id === msg.to);
  if (!source || !target) return;

  const isFromNcof = (msg.from === 'ncof' || msg.from === 'nef') && msg.type === 'NOTIFICATION';
  const color = getMessageColor(msg.type);
  const strokeColor = isFromNcof ? '#22d3ee' : color;
  const strokeWidth = isFromNcof ? 4 : 2;
  const path = calculatePath(source, target);

  const pathNode = signalsGroup.append('path')
    .attr('d', path)
    .attr('fill', 'none')
    .attr('visibility', 'hidden')
    .node() as SVGPathElement;

  const totalLength = pathNode.getTotalLength();

  const signalPath = signalsGroup.append('path')
    .attr('d', path)
    .attr('fill', 'none')
    .attr('stroke', strokeColor)
    .attr('stroke-width', strokeWidth)
    .attr('stroke-dasharray', `${totalLength} ${totalLength}`)
    .attr('stroke-dashoffset', totalLength);

  const arrowHead = signalsGroup.append('path')
    .attr('d', 'M -10 -5 L 0 0 L -10 5 z')
    .attr('fill', strokeColor);

  await signalPath.transition()
    .duration(800)
    .ease(d3.easeQuadInOut)
    .attr('stroke-dashoffset', 0)
    .tween('arrowTween', () => {
      return (t: number) => {
        const l = t * totalLength;
        const p = pathNode.getPointAtLength(l);
        const p1 = pathNode.getPointAtLength(Math.max(0, l - 1));
        const p2 = pathNode.getPointAtLength(Math.min(totalLength, l + 1));
        const angle = Math.atan2(p2.y - p1.y, p2.x - p1.x) * (180 / Math.PI);
        arrowHead.attr('transform', `translate(${p.x},${p.y}) rotate(${angle})`);
      };
    })
    .end();

  signalPath.remove();
  arrowHead.remove();
  pathNode.remove();

  if (msg.type === 'NOTIFICATION') {
    animateNotificationPulse(msg.to);
  } else if (msg.type === 'SUBSCRIBED') {
    store.addSubscription(msg.from, msg.to, msg?.subId, msg.type);
    renderLinks();
  } else if (msg.type === 'UNSUBSCRIBED') {
    store.removeSubscription(msg.from, msg.to, msg?.subId);
    renderLinks();
  } else if (msg.type === 'ANALYZING' && (msg.to === 'ncof' || msg.from === 'ncof')) {
    store.isAnalyzing = true;
  } else if (msg.type === 'ANALYZED' && (msg.to === 'ncof' || msg.from === 'ncof')) {
    store.isAnalyzing = false;
  }
};

/** Notification 수신 시 target 노드에 퍼지는 링 애니메이션 */
const animateNotificationPulse = (targetId: string) => {
  const target = store.nodes.find(n => n.id === targetId);
  if (!target) return;

  const color = getMessageColor('NOTIFICATION');
  // 2개의 원형 링이 순차적으로 퍼지면서 사라짐
  for (let i = 0; i < 2; i++) {
    const ring = signalsGroup.append('circle')
      .attr('cx', target.x)
      .attr('cy', target.y)
      .attr('r', 6)
      .attr('fill', 'none')
      .attr('stroke', color)
      .attr('stroke-width', 3 - i)
      .attr('opacity', 1);

    ring.transition()
      .delay(i * 200)
      .duration(600)
      .ease(d3.easeQuadOut)
      .attr('r', 55)
      .attr('opacity', 0)
      .remove();
  }

  // 노드 자체에 brief glow 효과 (rectangle highlight)
  const nodeRect = nodesGroup.selectAll<SVGGElement, NetworkNode>('.node-group')
    .filter((d: NetworkNode) => d.id === targetId)
    .select('rect');

  if (!nodeRect.empty()) {
    nodeRect.transition()
      .duration(200)
      .attr('class', 'fill-slate-800 stroke-2')
      .attr('stroke', color)
      .attr('stroke-width', 4)
      .transition()
      .duration(400)
      .attr('class', 'fill-slate-800 stroke-2')
      .attr('stroke', getNodeColor(target.type))
      .attr('stroke-width', 2);
  }
};

const getMessageColor = (type: Message['type']) => {
  switch (type) {
    case 'SUBSCRIBE': return '#60a5fa';
    case 'UNSUBSCRIBE': return '#f87171';
    case 'NOTIFICATION': return '#fbbf24';
    case 'SUBSCRIBED': return '#34d399';
    case 'UNSUBSCRIBED': return '#f43f5e';
    case 'ANALYZING': return '#60a5fa';
    case 'ANALYZED': return '#8b5cf6';
    default: return '#94a3b8';
  }
};

watch(() => store.isAnalyzing, (isAnalyzing) => {
  const analyzer = nodesGroup.select('.analyzer-group');
  if (isAnalyzing) {
    analyzer.transition().duration(500).style('opacity', 1);
  } else {
    analyzer.transition().duration(500).style('opacity', 0);
  }
});

defineExpose({ animateMessage });

watch(() => store.activeSubscriptions, renderLinks, { deep: true });

// const store = useNetworkStore();
const isSaving = ref(false);
const handleSave = async () => {
  isSaving.value = true;
  store.saveNodes();
  // Visual feedback
  await new Promise(resolve => setTimeout(resolve, 800));
  isSaving.value = false;
};

const btnStyle = computed(() => isSaving.value ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'border-white/10 text-slate-400 hover:bg-white/5')

const isResetting = ref(false);
const handleReset = async () => {
  isResetting.value = true;
  store.resetLayout();
  // Re-render with default positions
  nodesGroup.selectAll('.node-group').remove();
  linksGroup.selectAll('.link-line, .link-label').remove();
  topologyGroup.selectAll('.topology-edge, .topology-edge-label').remove();
  render();
  await new Promise(resolve => setTimeout(resolve, 800));
  isResetting.value = false;
};

</script>

<template>
  <div class="w-full h-full overflow-hidden relative">
    <svg ref="svgRef" class="w-full h-full select-none"></svg>
    <!-- <div class="absolute bottom-6 left-6 glass-panel rounded-xl p-4 text-[10px] space-y-2 pointer-events-none">
      <div class="font-bold text-slate-500 uppercase tracking-widest mb-2 border-b border-white/5 pb-1">Legend</div>
      <div class="flex items-center gap-3"><span class="w-2 h-2 bg-emerald-500 rounded-full"></span> RAN</div>
      <div class="flex items-center gap-3"><span class="w-2 h-2 bg-amber-500 rounded-full"></span> CN</div>
    </div> -->

    <div class="absolute top-2 right-2 z-999 flex items-center gap-2">
      <button @click="handleSave" title="Save Node Layout" class="hover:cursor-pointer p-2.5 rounded-xl border transition-all flex items-center gap-2" :class="btnStyle">
        <Save v-if="!isSaving" class="w-5 h-5" />
        <Clock6 v-else class="w-5 h-5 animate-spin" />
      </button>

      <button @click="handleReset" title="Reset Node Layout" class="hover:cursor-pointer p-2.5 rounded-xl border transition-all flex items-center gap-2" :class="isResetting ? 'bg-rose-500/20 border-rose-500/50 text-rose-400' : 'border-white/10 text-slate-400 hover:bg-white/5'">
        <Clock6 v-if="isResetting" class="w-5 h-5 animate-spin" />
        <Scan v-else class="text-xs font-bold"/>
      </button>
    </div>
  </div>
</template>

<style>
@keyframes flow {
  from {
    stroke-dashoffset: 20;
  }

  to {
    stroke-dashoffset: 0;
  }
}

.flowing-line {
  stroke-dasharray: 4, 4 !important;
  animation: flow 1s linear infinite !important;
}

/* AI Analyzer Ring — dashed circles flow to indicate AI analysis in progress */
@keyframes analyzer-flow {
  from { stroke-dashoffset: 8; }
  to   { stroke-dashoffset: 0; }
}

@keyframes analyzer-flow-outer {
  from { stroke-dashoffset: 0; }
  to   { stroke-dashoffset: 10; }
}

.analyzer-ring {
  animation: analyzer-flow 1.5s linear infinite !important;
}

.analyzer-ring-outer {
  animation: analyzer-flow-outer 2.5s linear infinite !important;
}

.topology-edge {
  stroke: rgba(148, 163, 184, 0.25);
  stroke-width: 1.5;
  stroke-dasharray: 5, 4;
}

/* 말풍선 코딩 텍스트 스크롤 */
@keyframes bubble-scroll {
  0%   { transform: translateY(0); }
  100% { transform: translateY(-25%); }
}

.bubble-scroll-inner {
  animation: bubble-scroll 6s linear infinite;
  will-change: transform;
}

.topology-edge-label {
  fill: rgba(148, 163, 184, 0.5);
  font-size: 8px;
  font-weight: 700;
  font-family: inherit;
  pointer-events: none;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}
</style>
