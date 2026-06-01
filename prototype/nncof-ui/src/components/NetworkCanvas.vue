<script setup lang="ts">
import { onMounted, ref, watch, onUnmounted } from 'vue';
import * as d3 from 'd3';
import { useNetworkStore } from '../store/network';
import type { Message, NetworkNode, Subscription, NodeEdge } from '../types';

const store = useNetworkStore();
const svgRef = ref<SVGSVGElement | null>(null);
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

  // Arrow markers
  svg.append('defs').append('marker')
    .attr('id', 'arrowhead')
    .attr('viewBox', '0 0 10 10')
    .attr('refX', 40)
    .attr('refY', 5)
    .attr('markerWidth', 6)
    .attr('markerHeight', 6)
    .attr('orient', 'auto-start-reverse')
    .append('path')
    .attr('d', 'M 0 0 L 10 5 L 0 10 z')
    .attr('fill', '#60a5fa');
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
    .attr('width', 64)
    .attr('height', 64)
    .attr('x', -32)
    .attr('y', -32)
    .attr('rx', 12)
    .attr('class', 'fill-slate-800 stroke-2')
    .attr('stroke', (d) => getNodeColor(d.type));

  nodeEnter.append('text')
    .attr('dy', 24)
    .attr('text-anchor', 'middle')
    .attr('class', 'text-[10px] font-bold fill-slate-400 select-none')
    .text((d) => d.name);

  nodeEnter.append('circle').attr('r', 12).attr('fill', (d) => getNodeColor(d.type)).attr('class', 'opacity-30').attr('filter', 'blur(4px)');
  nodeEnter.append('circle').attr('r', 6).attr('fill', 'white').attr('class', 'opacity-20');

  // AI Analyzer Ring (only for NCOF)
  const analyzer = nodeEnter.filter(d => d.type === 'NCOF')
    .append('g')
    .attr('class', 'analyzer-group')
    .style('opacity', 0);

  analyzer.append('circle')
    .attr('r', 40)
    .attr('fill', 'none')
    .attr('stroke', '#60a5fa')
    .attr('stroke-width', 2)
    .attr('stroke-dasharray', '4,4')
    .attr('class', 'analyzer-ring');

  analyzer.append('circle')
    .attr('r', 45)
    .attr('fill', 'none')
    .attr('stroke', '#3b82f6')
    .attr('stroke-width', 1)
    .attr('stroke-dasharray', '2,8')
    .attr('class', 'analyzer-ring-outer');

  analyzer.append('text')
    .attr('dy', -45)
    .attr('text-anchor', 'middle')
    .attr('class', 'text-[8px] font-black fill-blue-400 uppercase tracking-widest animate-pulse')
    .text('AI Analyzing...');

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

const renderLinks = () => {
  const links = linksGroup.selectAll<SVGPathElement, Subscription>('.link-line')
    .data(store.activeSubscriptions, (d) => d.id);

  links.enter()
    .append('path')
    .attr('marker-end', 'url(#arrowhead)')
    .merge(links as any)
    .attr('class', 'link-line fill-none stroke-blue-500/60 flowing-line')
    .attr('stroke-width', 2)
    .attr('d', (d: Subscription) => {
      const source = store.nodes.find(n => n.id === d.from);
      const target = store.nodes.find(n => n.id === d.to);
      if (!source || !target) return '';

      // Find index within the same from-to group
      const sameGroup = store.activeSubscriptions.filter(s => s.from === d.from && s.to === d.to);
      const index = sameGroup.findIndex(s => s.id === d.id);

      return calculatePath(source, target, index);
    });

  links.exit().remove();

  const labels = linksGroup.selectAll<SVGTextElement, Subscription>('.link-label')
    .data(store.activeSubscriptions, (d) => d.id);

  labels.enter()
    .append('text')
    .attr('class', 'link-label text-[8px] fill-blue-300 font-bold select-none')
    .attr('text-anchor', 'middle')
    .merge(labels as any)
    .text((d) => d.count && d.count > 1 ? `SUBSCRIBED (${d.count})` : 'SUBSCRIBED')
    .attr('transform', (d: Subscription) => {
      const source = store.nodes.find(n => n.id === d.from);
      const target = store.nodes.find(n => n.id === d.to);
      if (!source || !target) return '';

      const sameGroup = store.activeSubscriptions.filter(s => s.from === d.from && s.to === d.to);
      const index = sameGroup.findIndex(s => s.id === d.id);

      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const midX = (source.x + target.x) / 2;
      const midY = (source.y + target.y) / 2;

      // Calculate arc height (h) to place label at the center of the curve
      const distance = Math.sqrt(dx * dx + dy * dy) || 1;
      const baseDr = distance * 1.5;
      const dr = baseDr / (1 + index * 0.4);
      const h = dr - Math.sqrt(Math.max(0, dr * dr - (distance / 2) * (distance / 2)));

      // Perpendicular vector for offset
      const nx = -dy / distance;
      const ny = dx / distance;

      // Place label slightly above the arc peak
      const finalOffset = h + 10;

      return `translate(${midX + nx * finalOffset}, ${midY + ny * finalOffset})`;
    });

  labels.exit().remove();
};

const calculatePath = (source: NetworkNode, target: NetworkNode, index: number = 0) => {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.sqrt(dx * dx + dy * dy);

  // Vary curvature based on index
  // index 0 is baseline, index 1, 2... are more/less curved
  const baseDr = distance * 1.5;
  const dr = baseDr / (1 + index * 0.4);

  return `M${source.x},${source.y}A${dr},${dr} 0 0,1 ${target.x},${target.y}`;
};

const getNodeColor = (type: NetworkNode['type']) => {
  switch (type) {
    case 'NCOF': return '#e0e391';
    case 'RICF': return '#10b981';
    case 'AF': return '#f59e0b';
    case 'PCF': return '#4ed4cf';
    case 'SMF': return '#b572d6';
    case 'UPF': return '#b572d6';
    case 'UE': return '#3b82f6';
    case 'WIFI': return '#335182';
    case 'GNODEB': return '#756853';
    default: return '#64748b';
  }
};

const animateMessage = async (msg: Message) => {
  const source = store.nodes.find(n => n.id === msg.from);
  const target = store.nodes.find(n => n.id === msg.to);
  if (!source || !target) return;

  const color = getMessageColor(msg.type);
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
    .attr('stroke', color)
    .attr('stroke-width', 2)
    .attr('stroke-dasharray', `${totalLength} ${totalLength}`)
    .attr('stroke-dashoffset', totalLength);

  const arrowHead = signalsGroup.append('path')
    .attr('d', 'M -10 -5 L 0 0 L -10 5 z')
    .attr('fill', color);

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
    store.addSubscription(msg.from, msg.to, msg?.subId);
    renderLinks();
  } else if (msg.type === 'UNSUBSCRIBED') {
    store.removeSubscription(msg.from, msg.to, msg?.subId);
    renderLinks();
  } else if (msg.type === 'ANALIZING' && (msg.to === 'ncof' || msg.from === 'ncof')) {
    store.isAnalyzing = true;
  } else if (msg.type === 'ANALIZED' && (msg.to === 'ncof' || msg.from === 'ncof')) {
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
    case 'ANALIZING': return '#60a5fa';
    case 'ANALIZED': return '#8b5cf6';
    default: return '#94a3b8';
  }
};

watch(() => store.isAnalyzing, (isAnalyzing) => {
  const analyzer = nodesGroup.select('.analyzer-group');
  if (isAnalyzing) {
    analyzer.transition().duration(500).style('opacity', 1);
    animateAnalyzer();
  } else {
    analyzer.transition().duration(500).style('opacity', 0);
  }
});

const animateAnalyzer = () => {
  if (!store.isAnalyzing) return;

  nodesGroup.select('.analyzer-ring')
    .transition()
    .duration(2000)
    .ease(d3.easeLinear)
    .attrTween('transform', () => d3.interpolateString('rotate(0)', 'rotate(360)'))
    .on('end', animateAnalyzer);

  nodesGroup.select('.analyzer-ring-outer')
    .transition()
    .duration(3000)
    .ease(d3.easeLinear)
    .attrTween('transform', () => d3.interpolateString('rotate(360)', 'rotate(0)'));
};

defineExpose({ animateMessage });

watch(() => store.activeSubscriptions, renderLinks, { deep: true });
</script>

<template>
  <div class="w-full h-full overflow-hidden relative">
    <svg ref="svgRef" class="w-full h-full select-none"></svg>
    <!-- <div class="absolute bottom-6 left-6 glass-panel rounded-xl p-4 text-[10px] space-y-2 pointer-events-none"> -->
    <!-- <div class="font-bold text-slate-500 uppercase tracking-widest mb-2 border-b border-white/5 pb-1">Legend</div> -->
    <!-- <div class="flex items-center gap-3"><span class="w-2 h-2 bg-emerald-500 rounded-full"></span> RAN</div> -->
    <!-- <div class="flex items-center gap-3"><span class="w-2 h-2 bg-amber-500 rounded-full"></span> CN</div> -->
    <!-- </div> -->
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

.topology-edge {
  stroke: rgba(148, 163, 184, 0.25);
  stroke-width: 1.5;
  stroke-dasharray: 5, 4;
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
