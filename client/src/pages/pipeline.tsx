import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Activity, Cpu, Link2, Server, Brain, Database,
  CheckCircle2, Circle, Loader2, AlertCircle, Clock,
  BarChart3, Layers, Zap, RefreshCw, KeyRound,
  ShieldAlert, ShieldCheck, Copy, ExternalLink
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface SystemStatus {
  ibkr: {
    connected: boolean;
    market_count: number;
    port_open: boolean;
    auth_required: boolean;
    auth_error: string | null;
  };
  ollama: { online: boolean; models: string[]; url: string };
  tunnel: { url: string; ngrok_url: string | null; configured: boolean };
  pipeline: {
    status: string; phase: string; message: string;
    progress: number; total_markets: number; pairs_found: number;
    is_scanning: boolean; last_scan_time: string | null;
  };
  colab: Record<string, any>;
  markets: { total: number; by_platform: Record<string, number> };
  timestamp: string;
}

const COLAB_CELLS = [
  { id: 1, label: "Environment Setup", desc: "Installing dependencies, configuring GPU" },
  { id: 2, label: "Fetching Markets", desc: "Downloading all markets from backend API" },
  { id: 3, label: "Binary Filter", desc: "Removing non-binary markets (3+ outcomes)" },
  { id: 4, label: "Noise Reduction", desc: "Filtering sports score/stats micro-markets" },
  { id: 5, label: "Loading Bi-Encoder", desc: "BAAI/bge-m3 embedding model on GPU" },
  { id: 6, label: "Generating Embeddings", desc: "Encoding all market titles into vectors" },
  { id: 7, label: "Building FAISS Index", desc: "IndexFlatIP on GPU for fast ANN search" },
  { id: 8, label: "Finding Candidates", desc: "Top-50 nearest neighbors per market" },
  { id: 9, label: "Loading Reranker", desc: "BAAI/bge-reranker-v2-m3 cross-encoder" },
  { id: 10, label: "Reranking Pairs", desc: "Cross-encoder scores > 0.5 threshold" },
  { id: 11, label: "LLM Verification", desc: "Ollama verifies semantic equivalence" },
  { id: 12, label: "Posting Results", desc: "Top-2000 pairs sent to backend API" },
];

function StatusDot({ ok, pulse }: { ok: boolean; pulse?: boolean }) {
  return (
    <span className={`inline-flex h-2.5 w-2.5 rounded-full ${ok ? "bg-green-500" : "bg-red-500"} ${pulse && ok ? "animate-pulse" : ""}`} />
  );
}

function SystemCard({
  icon: Icon, title, status, children
}: { icon: any; title: string; status: "online" | "offline" | "unknown" | "warning"; children: React.ReactNode }) {
  const colors = { online: "text-green-400", offline: "text-red-400", unknown: "text-amber-400", warning: "text-amber-400" };
  const labels = { online: "Online", offline: "Offline", unknown: "Ready", warning: "Auth Needed" };
  return (
    <Card className={`border-border/50 bg-card/80 backdrop-blur ${status === "warning" ? "ring-1 ring-amber-500/30" : ""}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2 text-muted-foreground">
            <Icon className="w-4 h-4" />
            {title}
          </CardTitle>
          <span className={`text-xs font-mono font-semibold ${colors[status]}`}>
            {labels[status]}
          </span>
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function IBKRCard({ ibkr }: { ibkr: SystemStatus["ibkr"] | undefined }) {
  const queryClient = useQueryClient();
  const [reloginState, setReloginState] = useState<"idle" | "probing" | "restarting" | "done" | "manual">("idle");
  const [reloginMsg, setReloginMsg] = useState("");

  const probeMutation = useMutation({
    mutationFn: async () => {
      setReloginState("probing");
      const r = await fetch("/api/ibkr-probe");
      return r.json();
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["/api/system-status"] });
      if (data.authenticated) {
        setReloginState("done");
        setReloginMsg("Gateway is authenticated.");
      } else {
        setReloginState("idle");
        setReloginMsg(data.error ?? "Not authenticated.");
      }
    },
  });

  const reloginMutation = useMutation({
    mutationFn: async () => {
      setReloginState("restarting");
      const r = await fetch("/api/ibkr-relogin", { method: "POST" });
      return r.json();
    },
    onSuccess: (data) => {
      if (data.status === "restarting") {
        setReloginState("done");
        setReloginMsg(data.message);
      } else {
        setReloginState("manual");
        setReloginMsg(data.message);
      }
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["/api/system-status"] }), 5000);
    },
  });

  const authRequired = ibkr?.auth_required ?? false;
  const connected = ibkr?.connected ?? false;
  const portOpen = ibkr?.port_open ?? false;
  // "authenticated" = probe ran and confirmed session is valid
  const probedAuth = reloginState === "done" && reloginMsg.includes("authenticated");

  const cardStatus = authRequired
    ? "warning"
    : connected
    ? "online"
    : portOpen
    ? "unknown"   // port up, just no markets fetched yet
    : "offline";

  return (
    <SystemCard icon={Server} title="IBKR Gateway" status={cardStatus}>
      <div className="flex items-center gap-2 mt-1">
        <StatusDot ok={connected} />
        <span className="text-lg font-mono font-bold">
          {ibkr?.market_count?.toLocaleString() ?? "—"}
        </span>
        <span className="text-xs text-muted-foreground">markets</span>
      </div>
      <p className="text-xs text-muted-foreground mt-1">
        {connected
          ? "ForecastEx data streaming"
          : portOpen
          ? "Gateway up — run Scan to fetch markets"
          : "Gateway offline or not reachable"}
      </p>

      {authRequired && (
        <div className="mt-3 space-y-2">
          <div className="flex items-center gap-1.5 text-xs text-amber-400">
            <ShieldAlert className="w-3.5 h-3.5" />
            {ibkr?.auth_error ?? "Login required"}
          </div>

          {reloginState === "idle" && (
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs border-amber-500/40 text-amber-400 hover:bg-amber-500/10"
                onClick={() => probeMutation.mutate()}
              >
                <RefreshCw className="w-3 h-3 mr-1" />
                Check Auth
              </Button>
              <Button
                size="sm"
                className="h-7 text-xs bg-amber-500/20 text-amber-300 border border-amber-500/30 hover:bg-amber-500/30"
                onClick={() => reloginMutation.mutate()}
              >
                <KeyRound className="w-3 h-3 mr-1" />
                Re-login
              </Button>
            </div>
          )}

          {(reloginState === "probing" || reloginState === "restarting") && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {reloginState === "probing" ? "Checking auth…" : "Restarting Gateway…"}
            </div>
          )}

          {reloginState === "done" && (
            <div className="flex items-center gap-1.5 text-xs text-green-400">
              <ShieldCheck className="w-3.5 h-3.5" />
              {reloginMsg}
            </div>
          )}

          {reloginState === "manual" && (
            <div className="text-xs text-amber-300/80 space-y-1">
              <p>{reloginMsg}</p>
              <p className="text-muted-foreground">Docker socket not mounted yet — takes effect after next rebuild.</p>
            </div>
          )}
        </div>
      )}

      {!authRequired && reloginState === "idle" && (
        <Button
          size="sm"
          variant="ghost"
          className="h-6 text-xs text-muted-foreground mt-2 px-1"
          onClick={() => probeMutation.mutate()}
          disabled={probeMutation.isPending}
        >
          <RefreshCw className="w-3 h-3 mr-1" />
          Probe
        </Button>
      )}

      {reloginMsg && !authRequired && (
        <p className="text-xs text-muted-foreground mt-1">{reloginMsg}</p>
      )}
    </SystemCard>
  );
}

function TunnelCard({ tunnel }: { tunnel: SystemStatus["tunnel"] | undefined }) {
  const { toast } = useToast();
  const ngrokUrl = tunnel?.ngrok_url;
  const configured = tunnel?.configured ?? false;

  const copy = () => {
    if (!ngrokUrl) return;
    navigator.clipboard.writeText(ngrokUrl).then(() =>
      toast({ title: "Copied", description: "ngrok URL copied to clipboard" })
    );
  };

  return (
    <SystemCard icon={Link2} title="ngrok Tunnel" status={configured ? "online" : "offline"}>
      {ngrokUrl ? (
        <div className="mt-1 space-y-2">
          <p className="text-[11px] font-mono text-foreground break-all leading-tight">{ngrokUrl}</p>
          <div className="flex gap-1.5">
            <Button size="sm" variant="outline" className="h-6 text-xs px-2 flex-1" onClick={copy}>
              <Copy className="w-3 h-3 mr-1" /> Copy
            </Button>
            <Button size="sm" variant="outline" className="h-6 text-xs px-2 flex-1" asChild>
              <a href={ngrokUrl} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="w-3 h-3 mr-1" /> Open
              </a>
            </Button>
          </div>
          <p className="text-[10px] text-muted-foreground">Bookmark this — changes on ngrok restart</p>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground mt-1">ngrok not running or no tunnel active</p>
      )}
    </SystemCard>
  );
}

export default function PipelinePage() {
  const { data: status, isLoading } = useQuery<SystemStatus>({
    queryKey: ["/api/system-status"],
    queryFn: () => fetch("/api/system-status").then(r => r.json()),
    refetchInterval: 15_000,
  });

  const pipeline = status?.pipeline;
  const colab = status?.colab ?? {};
  const colabCell = colab.cell ?? 0;
  const colabRunning = colab.running ?? false;
  const isScanning = pipeline?.is_scanning ?? false;

  const getCellState = (cellId: number): "done" | "active" | "pending" => {
    if (!colabRunning && colabCell === 0) return "pending";
    if (cellId < colabCell) return "done";
    if (cellId === colabCell) return "active";
    return "pending";
  };

  return (
    <div className="container mx-auto px-4 py-6 max-w-6xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Activity className="w-6 h-6 text-primary" />
          Pipeline & System Status
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Live health of all connected services and the Colab processing pipeline
        </p>
      </div>

      {/* System Health Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {/* IBKR — smart card with auth probe */}
        <IBKRCard ibkr={status?.ibkr} />

        {/* Ollama */}
        <SystemCard
          icon={Brain}
          title="Ollama LLM"
          status={status?.ollama.online ? "online" : "offline"}
        >
          {status?.ollama.models && status.ollama.models.length > 0 ? (
            <div className="space-y-1 mt-1">
              {status.ollama.models.slice(0, 2).map(m => (
                <div key={m} className="flex items-center gap-1.5">
                  <StatusDot ok={true} pulse />
                  <span className="text-xs font-mono text-foreground truncate max-w-[160px]">{m}</span>
                </div>
              ))}
              {status.ollama.models.length > 2 && (
                <p className="text-xs text-muted-foreground">+{status.ollama.models.length - 2} more</p>
              )}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground mt-1">
              {status?.ollama.online ? "No models loaded" : "Service offline"}
            </p>
          )}
        </SystemCard>

        {/* Tunnel */}
        <SystemCard
          icon={Link2}
          title="Tailscale Tunnel"
          status={status?.tunnel.configured ? "online" : "unknown"}
        >
          <p className="text-xs font-mono text-foreground mt-1 truncate">
            {status?.tunnel.url ?? "Not configured"}
          </p>
          <p className="text-xs text-muted-foreground mt-1">Public HTTPS endpoint</p>
        </SystemCard>

        {/* Backend */}
        <SystemCard icon={Cpu} title="Backend API" status="online">
          <div className="mt-1">
            <div className="flex items-center gap-2">
              <StatusDot ok={true} pulse />
              <span className="text-xs text-foreground">FastAPI running</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {status?.markets.total?.toLocaleString() ?? "—"} markets cached
            </p>
          </div>
        </SystemCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Pipeline Scan Status */}
        <div className="lg:col-span-1 space-y-4">
          <Card className="border-border/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-primary" />
                Scan Pipeline
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-2">
                {isScanning ? (
                  <Loader2 className="w-4 h-4 text-primary animate-spin" />
                ) : pipeline?.status === "complete" ? (
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                ) : pipeline?.status === "error" ? (
                  <AlertCircle className="w-4 h-4 text-red-500" />
                ) : (
                  <Circle className="w-4 h-4 text-muted-foreground" />
                )}
                <span className="font-medium text-sm capitalize">{pipeline?.status ?? "idle"}</span>
                {isScanning && (
                  <Badge variant="secondary" className="text-xs animate-pulse">Live</Badge>
                )}
              </div>

              {(isScanning || (pipeline?.progress ?? 0) > 0) && (
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{pipeline?.phase}</span>
                    <span>{pipeline?.progress ?? 0}%</span>
                  </div>
                  <Progress value={pipeline?.progress ?? 0} className="h-1.5" />
                  <p className="text-xs text-muted-foreground">{pipeline?.message}</p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-border/50">
                <div>
                  <p className="text-2xl font-mono font-bold">
                    {status?.markets.total?.toLocaleString() ?? "—"}
                  </p>
                  <p className="text-xs text-muted-foreground">Total Markets</p>
                </div>
                <div>
                  <p className="text-2xl font-mono font-bold text-primary">
                    {pipeline?.pairs_found?.toLocaleString() ?? "—"}
                  </p>
                  <p className="text-xs text-muted-foreground">Pairs Found</p>
                </div>
              </div>

              {pipeline?.last_scan_time && (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground border-t border-border/50 pt-2">
                  <Clock className="w-3.5 h-3.5" />
                  Last scan: {new Date(pipeline.last_scan_time).toLocaleTimeString()}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Market counts by platform */}
          <Card className="border-border/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Database className="w-4 h-4 text-primary" />
                Markets by Platform
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {status?.markets.by_platform && Object.keys(status.markets.by_platform).length > 0 ? (
                Object.entries(status.markets.by_platform)
                  .sort(([, a], [, b]) => b - a)
                  .map(([platform, count]) => (
                    <div key={platform} className="flex items-center justify-between">
                      <span className="text-sm capitalize text-muted-foreground">{platform}</span>
                      <span className="text-sm font-mono font-semibold">{count.toLocaleString()}</span>
                    </div>
                  ))
              ) : (
                <p className="text-xs text-muted-foreground">No markets cached yet. Run a scan first.</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: Colab Cell Progress */}
        <div className="lg:col-span-2">
          <Card className="border-border/50 h-full">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Layers className="w-4 h-4 text-primary" />
                  Colab GPU Pipeline
                </CardTitle>
                {colabRunning && (
                  <Badge className="bg-green-500/10 text-green-400 border-green-500/20 animate-pulse">
                    <Zap className="w-3 h-3 mr-1" />
                    Running
                  </Badge>
                )}
                {!colabRunning && colabCell > 0 && (
                  <Badge variant="secondary" className="text-xs">
                    <CheckCircle2 className="w-3 h-3 mr-1" />
                    Complete
                  </Badge>
                )}
                {!colabRunning && colabCell === 0 && (
                  <Badge variant="outline" className="text-xs text-muted-foreground">
                    Waiting for next run
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-1">
                {COLAB_CELLS.map((cell) => {
                  const state = getCellState(cell.id);
                  return (
                    <div
                      key={cell.id}
                      className={`flex items-start gap-3 p-2.5 rounded-md transition-colors ${
                        state === "active"
                          ? "bg-primary/10 border border-primary/20"
                          : state === "done"
                          ? "opacity-60"
                          : "opacity-40"
                      }`}
                    >
                      <div className="mt-0.5 flex-shrink-0">
                        {state === "done" ? (
                          <CheckCircle2 className="w-4 h-4 text-green-500" />
                        ) : state === "active" ? (
                          <Loader2 className="w-4 h-4 text-primary animate-spin" />
                        ) : (
                          <div className="w-4 h-4 rounded-full border border-border flex items-center justify-center">
                            <span className="text-[9px] text-muted-foreground">{cell.id}</span>
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-medium ${state === "active" ? "text-foreground" : "text-muted-foreground"}`}>
                            {cell.label}
                          </span>
                          {state === "active" && colab.cell_detail && (
                            <span className="text-xs text-primary truncate">{colab.cell_detail}</span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground/70 mt-0.5">{cell.desc}</p>
                      </div>
                    </div>
                  );
                })}
              </div>

              {colab.message && (
                <div className="mt-4 p-3 rounded-md bg-muted/50 border border-border/50">
                  <p className="text-xs text-muted-foreground font-mono">{colab.message}</p>
                </div>
              )}

              <div className="mt-4 p-3 rounded-md bg-muted/30 text-xs text-muted-foreground border border-border/30">
                <p className="font-medium text-foreground/70 mb-1">How to trigger:</p>
                <p>Hit <span className="font-mono text-foreground/80">Scan</span> on the Opportunities page — fetches all markets, patches the notebook, opens Colab as <span className="font-mono">bamove@gmail.com</span>, runs LLM verification, and pushes results.</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
