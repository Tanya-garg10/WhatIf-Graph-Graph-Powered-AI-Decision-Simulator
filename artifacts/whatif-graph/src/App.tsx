import { useMemo, useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useGetDependencyGraph, useSimulateScenario, getGetDependencyGraphQueryKey } from '@workspace/api-client-react';
import { Activity, AlertTriangle, ArrowRight, Boxes, Braces, ChevronRight, CircleDot, Cloud, Database, GitBranch, LoaderCircle, Network, Play, RefreshCw, Server, Sparkles, Waypoints } from 'lucide-react';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';
import './index.css';

const queryClient = new QueryClient();
type GraphNode = { id: string; name: string; type: string; description: string; status: string };
type GraphResponse = { nodes: GraphNode[]; edges: { source: string; target: string; relationship: string }[]; backend: 'falkordb' | 'demo'; databaseConnected: boolean; graphName: string };
type SimulationResponse = { scenario: string; triggerNode: string; eventType: string; risk: string; baselineComponentCount: number; affectedComponentCount: number; affectedNodes: { id: string; name: string; type: string; severity: string; reason: string; path: string[] }[]; bottlenecks: string[]; mitigations: { title: string; detail: string; basis: string }[]; explanation: string; backend: 'falkordb' | 'demo'; databaseConnected: boolean };
const starterScenarios = [
  'What happens if the Payment Service goes down?',
  'What if the database is delayed by two days?',
  'What if the Engineering Team loses one member?',
  'What if the Inventory Service is unavailable?',
];

const nodePositions = [
  [50, 48], [25, 24], [75, 21], [20, 68], [79, 68],
  [45, 83], [62, 17], [37, 16], [88, 44], [11, 43],
  [61, 74], [35, 57], [68, 47], [50, 28],
];

function typeIcon(type: string) {
  const value = type.toLowerCase();
  if (value.includes('data') || value.includes('database') || value.includes('db')) return <Database size={13} />;
  if (value.includes('queue') || value.includes('broker')) return <Activity size={13} />;
  if (value.includes('external') || value.includes('third')) return <Cloud size={13} />;
  if (value.includes('api') || value.includes('gateway')) return <Braces size={13} />;
  if (value.includes('service') || value.includes('worker')) return <Server size={13} />;
  return <Boxes size={13} />;
}

function typeClass(type: string) {
  const value = type.toLowerCase();
  if (value.includes('data') || value.includes('database') || value.includes('db')) return 'database';
  if (value.includes('queue') || value.includes('broker')) return 'queue';
  if (value.includes('external') || value.includes('third')) return 'external';
  if (value.includes('service') || value.includes('api') || value.includes('worker') || value.includes('gateway')) return 'service';
  return '';
}

function GraphBoard({ nodes, edges, selectedNode, onSelect, affectedIds, isLoading }: {
  nodes: GraphNode[];
  edges: { source: string; target: string; relationship: string }[];
  selectedNode: GraphNode | undefined;
  onSelect: (node: GraphNode) => void;
  affectedIds: string[];
  isLoading: boolean;
}) {
  const positions = useMemo(() => {
    const map = new Map<string, [number, number]>();
    nodes.forEach((node, index) => {
      const point = nodePositions[index % nodePositions.length];
      const cycle = Math.floor(index / nodePositions.length);
      map.set(node.id, [Math.min(91, Math.max(9, point[0] + cycle * 2)), Math.min(87, Math.max(12, point[1] - cycle * 2))]);
    });
    return map;
  }, [nodes]);
  const connected = selectedNode ? edges.filter(edge => edge.source === selectedNode.id || edge.target === selectedNode.id) : [];

  if (isLoading) return <div className="skeleton skeleton-graph" aria-label="Loading dependency graph" />;
  if (!nodes.length) return <div className="graph-canvas"><div className="graph-empty"><div><strong>No graph nodes available</strong>The graph endpoint returned an empty dependency graph.</div></div></div>;

  return (
    <div className="graph-canvas" data-testid="graph-canvas">
      <svg className="graph-svg" viewBox="0 0 1000 580" preserveAspectRatio="none" aria-label="Dependency connections">
        <defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#59627d" /></marker></defs>
        {edges.map((edge, index) => {
          const source = positions.get(edge.source);
          const target = positions.get(edge.target);
          if (!source || !target) return null;
          const active = selectedNode && (selectedNode.id === edge.source || selectedNode.id === edge.target);
          return <g key={`${edge.source}-${edge.target}-${index}`}>
            <line className={`edge${active ? ' active' : ''}`} x1={`${source[0]}%`} y1={`${source[1]}%`} x2={`${target[0]}%`} y2={`${target[1]}%`} markerEnd="url(#arrow)" />
          </g>;
        })}
      </svg>
      {nodes.map((node) => {
        const point = positions.get(node.id) ?? [50, 50];
        const isSelected = selectedNode?.id === node.id;
        return <button
          key={node.id}
          className={`graph-node${isSelected ? ' selected' : ''}${affectedIds.includes(node.id) ? ' impacted' : ''}`}
          style={{ left: `${point[0]}%`, top: `${point[1]}%` }}
          onClick={() => onSelect(node)}
          aria-pressed={isSelected}
          title={`${node.name} — ${node.description}`}
          data-testid={`graph-node-${node.id}`}
        >
          <span className={`node-icon ${typeClass(node.type)}`}>{typeIcon(node.type)}</span>
          <span className="node-copy"><span className="node-name">{node.name}</span><span className="node-type">{node.type}</span></span>
        </button>;
      })}
    </div>
  );
}

function SourceStatus({ backend, connected }: { backend?: string; connected?: boolean }) {
  const isDemo = backend === 'demo';
  const label = backend ? (isDemo ? 'DEMO GRAPH' : 'FALKORDB') : 'SOURCE UNKNOWN';
  const connection = isDemo ? 'LOCAL ONLY' : connected ? 'CONNECTED' : connected === false ? 'DB OFFLINE' : 'CHECKING';
  return <span className="status-pill" data-testid="status-graph-source"><span className={`status-dot${isDemo || connected === false ? ' demo' : ''}`} />{label}<span style={{ color: '#58627a' }}>/</span>{connection}</span>;
}

function SelectedNodePanel({ node, edges, nodes }: { node?: GraphNode; edges: { source: string; target: string; relationship: string }[]; nodes: GraphNode[] }) {
  const related = node ? edges.filter(edge => edge.source === node.id || edge.target === node.id) : [];
  return <section className="panel selected-panel" aria-label="Selected node details">
    <div className="selected-top">
      <div className="section-heading"><CircleDot size={14} /> Node inspection</div>
      {node && <span className="step-label">{related.length} CONNECTION{related.length === 1 ? '' : 'S'}</span>}
    </div>
    {node ? <>
      <div className="selected-title" data-testid="text-selected-node">{node.name}</div>
      <div className="selected-type">{node.type} · {node.status}</div>
      <p className="selected-desc">{node.description}</p>
      <div className="connection-list">
        {related.length ? related.map((edge, index) => {
          const otherId = edge.source === node.id ? edge.target : edge.source;
          const other = nodes.find(item => item.id === otherId);
          return <div className="connection-item" key={`${otherId}-${index}`}><GitBranch size={11} /><span>{edge.source === node.id ? 'Depends on' : 'Feeds'}</span><strong>{other?.name ?? otherId}</strong><span>{edge.relationship}</span></div>;
        }) : <div className="empty-inspect">No connections are recorded for this node.</div>}
      </div>
    </> : <p className="empty-inspect">Select a node in the graph to inspect its status, description, and direct connections.</p>}
  </section>;
}

function SimulationReport({ result, pending }: { result?: { scenario: string; triggerNode: string; eventType: string; risk: string; baselineComponentCount: number; affectedComponentCount: number; affectedNodes: { id: string; name: string; type: string; severity: string; reason: string; path: string[] }[]; bottlenecks: string[]; mitigations: { title: string; detail: string; basis: string }[]; explanation: string; backend: 'falkordb' | 'demo'; databaseConnected: boolean; analysisMode: 'ai_assisted' | 'rule_based' }; pending: boolean }) {
  if (pending) return <section className="panel report-panel" aria-label="Simulation report loading">
    <div className="report-top"><div className="section-heading"><Activity size={14} /> Impact report</div><span className="report-badge">RUNNING</span></div>
    <div className="report-placeholder"><div className="placeholder-icon"><LoaderCircle size={17} /></div><strong>Tracing dependency paths</strong><p>Evaluating the scenario against the baseline graph.</p></div>
  </section>;
  if (!result) return <section className="panel report-panel" aria-label="Simulation impact report">
    <div className="report-top"><div className="section-heading"><Activity size={14} /> Impact report</div><span className="report-badge">AWAITING SCENARIO</span></div>
    <div className="report-placeholder"><div className="placeholder-icon"><Waypoints size={17} /></div><strong>Baseline vs. simulated impact</strong><p>Run a scenario to see affected components, risk, bottlenecks, and suggested mitigations.</p></div>
  </section>;

  return <section className="panel report-panel" aria-label="Simulation impact report">
    <div className="report-top"><div className="section-heading"><Activity size={14} /> Impact report</div><span className="report-badge">{result.backend.toUpperCase()} · {result.analysisMode === 'ai_assisted' ? 'AI ASSISTED' : 'RULE-BASED'}</span></div>
    <div className="report-content" key={`${result.scenario}-${result.triggerNode}`}>
      <div className="report-scenario">{result.scenario}</div>
      <div className="impact-reason" style={{ margin: '8px 0 0' }}>Trigger node: <strong style={{ color: '#c9c5eb' }}>{result.triggerNode}</strong></div>
      <div className="risk-line">
        <div><span className="risk-kicker">Overall risk · {result.eventType.replace('_', ' ')}</span><span className="risk-value">{result.risk}</span></div>
        <span className={`risk-chip ${result.risk}`}>{result.risk}</span>
      </div>
      <div className="impact-bars">
        <div className="impact-stat"><span>Baseline components</span><strong>{result.baselineComponentCount}</strong></div>
        <div className="impact-stat sim"><span>Affected components</span><strong>{result.affectedComponentCount}</strong></div>
      </div>
      <div className="report-divider" />
      <div className="subhead">Affected nodes <small>GRAPH-DERIVED FACTS</small></div>
      {result.affectedNodes.length ? <div className="affected-list">
        {result.affectedNodes.map((item) => <div key={item.id}>
          <div className="affected-row"><i className={`severity ${item.severity}`} /><span className="affected-name">{item.name}</span><span className="affected-type">{item.type}</span><span className="affected-type">{item.severity}</span></div>
          <p className="impact-reason">{item.reason}{item.path.length > 0 && <> · Path: {item.path.join(' → ')}</>}</p>
        </div>)}
      </div> : <p className="empty-inspect">No downstream nodes were identified as affected.</p>}
      {result.bottlenecks.length > 0 && <>
        <div className="report-divider" />
        <div className="subhead">Bottlenecks <small>GRAPH-DERIVED FACTS</small></div>
        {result.bottlenecks.map((item, index) => <div className="bottleneck-item" key={`${item}-${index}`}><AlertTriangle size={11} />{item}</div>)}
      </>}
      <div className="report-divider" />
      <div className="subhead">Mitigation ideas <small>HEURISTIC RECOMMENDATIONS</small></div>
      {result.mitigations.length ? result.mitigations.map((item, index) => <div className="mitigation-box" key={`${item.title}-${index}`}>
        <div className="mitigation-title">{item.title}<span className="heuristic">{item.basis}</span></div><p>{item.detail}</p>
      </div>) : <p className="empty-inspect">No heuristic mitigation ideas returned.</p>}
      <div className="report-divider" />
      <div className="subhead">Analysis <small>SIMULATION EXPLANATION</small></div>
      <p className="explanation">{result.explanation}</p>
    </div>
  </section>;
}

function Home() {
  const graphQuery = useGetDependencyGraph({ query: { queryKey: getGetDependencyGraphQueryKey() } });
  const simulation = useSimulateScenario();
  const graph = graphQuery.data;
  const [scenario, setScenario] = useState('');
  const [selectedId, setSelectedId] = useState<string>();
  const [validation, setValidation] = useState('');
  const selectedNode = graph?.nodes.find(node => node.id === selectedId);
  const result = simulation.data;
  const affectedIds = result?.affectedNodes.map(node => node.id) ?? [];

  const runScenario = (value = scenario) => {
    const trimmed = value.trim();
    if (trimmed.length < 5) {
      setValidation('Describe a scenario using at least 5 characters.');
      return;
    }
    if (trimmed.length > 500) {
      setValidation('Scenarios must be 500 characters or fewer.');
      return;
    }
    setValidation('');
    setScenario(trimmed);
    simulation.reset();
    simulation.mutate({ data: { scenario: trimmed } });
  };

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand-wrap">
        <div className="brand"><span className="brand-mark"><Network size={16} strokeWidth={2.4} /></span>WhatIf Graph</div>
        <span className="brand-sub">SYSTEMS INTELLIGENCE</span>
      </div>
      <div className="top-actions"><SourceStatus backend={graph?.backend} connected={graph?.databaseConnected} /><div className="avatar" aria-label="Engineering workspace">EW</div></div>
    </header>
    <main className="workspace">
      <div className="crumb"><span>Workspace</span><ChevronRight size={12} /><b>Dependency graph</b></div>
      <div className="page-heading">
        <div><h1 className="page-title">Change impact simulator</h1><p className="page-subtitle">Trace the blast radius before the change hits production.</p></div>
        <div className="inline-meta"><span>{graph?.graphName ?? 'Dependency graph'}</span><span className="meta-bar" /><span>{graph ? `${graph.nodes.length} NODES · ${graph.edges.length} EDGES` : 'GRAPH DATA'}</span></div>
      </div>
      {graphQuery.isError ? <div className="api-error" role="alert" data-testid="status-graph-error">
        <strong>Could not load the dependency graph</strong>
        The graph API returned an error. Check the service and retry; no local graph is substituted.
        <br /><button className="retry-button" onClick={() => graphQuery.refetch()} data-testid="button-retry-graph"><RefreshCw size={11} style={{ verticalAlign: 'middle', marginRight: 5 }} />Retry connection</button>
      </div> : null}
      <div className="workspace-grid" style={{ marginTop: graphQuery.isError ? 16 : 0 }}>
        <section className="panel graph-panel" aria-label="Dependency graph visualization">
          <div className="panel-head">
            <div className="section-heading"><GitBranch size={14} /> System dependency graph</div>
            <div className="graph-toolbar"><span className="toolbar-tag">{graph?.backend === 'falkordb' ? 'LIVE GRAPH' : graph?.backend === 'demo' ? 'DEMO MODE' : 'CONNECTING'}</span><span>{graph?.nodes.length ?? '—'} nodes</span></div>
          </div>
          <GraphBoard nodes={graph?.nodes ?? []} edges={graph?.edges ?? []} selectedNode={selectedNode} onSelect={node => setSelectedId(node.id)} affectedIds={affectedIds} isLoading={graphQuery.isLoading} />
          <div className="graph-legend">
            <div className="legend">
              <span className="legend-item"><i className="legend-mark" />Application</span>
              <span className="legend-item"><i className="legend-mark service" />Service</span>
              <span className="legend-item"><i className="legend-mark database" />Data store</span>
              <span className="legend-item"><i className="legend-mark queue" />Queue</span>
            </div>
            <span className="zoom-label">SELECT A NODE TO INSPECT</span>
          </div>
        </section>
        <div className="side-stack">
          <section className="panel scenario-panel">
            <div className="scenario-header"><div className="section-heading"><Sparkles size={14} /> Run a scenario</div><span className="step-label">{graph?.aiConfigured ? 'AI READY' : 'RULE-BASED'}</span></div>
            <p className="scenario-hint">Describe a hypothetical change or failure. We'll trace its downstream impact across this graph.</p>
            <textarea className="scenario-input" value={scenario} onChange={event => { setScenario(event.target.value); setValidation(''); }} placeholder="e.g. What if the payment service goes down?" maxLength={500} aria-label="Describe a hypothetical scenario" data-testid="input-scenario" />
            <div className="suggestion-label">Try a scenario</div>
            <div className="suggestions">{starterScenarios.map(item => <button className="suggestion" key={item} onClick={() => runScenario(item)} disabled={simulation.isPending} data-testid={`button-scenario-${starterScenarios.indexOf(item)}`}>{item}</button>)}</div>
            {validation && <p className="scenario-error" role="alert">{validation}</p>}
            {simulation.isError && <p className="scenario-error" role="alert">Simulation failed. Your graph is unchanged; edit the scenario or try again.</p>}
            <button className="run-button" onClick={() => runScenario()} disabled={simulation.isPending || graphQuery.isLoading || graphQuery.isError || !graph?.nodes.length} data-testid="button-run-simulation">
              {simulation.isPending ? <><LoaderCircle size={13} />Tracing impact…</> : <><Play size={12} fill="currentColor" />Run simulation<ArrowRight size={13} /></>}
            </button>
          </section>
          <SimulationReport result={result} pending={simulation.isPending} />
        </div>
        <SelectedNodePanel node={selectedNode} edges={graph?.edges ?? []} nodes={graph?.nodes ?? []} />
      </div>
      {graph && <div className="inline-meta" style={{ justifyContent: 'flex-end', marginTop: 14 }}><span>GRAPH SOURCE: {graph.backend.toUpperCase()}</span><span className="meta-bar" /><span>DATABASE {graph.databaseConnected ? 'CONNECTED' : 'NOT CONNECTED'}</span></div>}
    </main>
  </div>;
}

function Router() {
  return <RoutedErrorBoundary><Switch><Route path="/" component={Home} /><Route component={NotFound} /></Switch></RoutedErrorBoundary>;
}

function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

function App() {
  return <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}><Router /></WouterRouter>
      <Toaster />
    </TooltipProvider>
  </QueryClientProvider>;
}

export default App;
