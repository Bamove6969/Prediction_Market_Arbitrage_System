import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FishSymbol, CloudRain, Info, TrendingUp, AlertCircle, ArrowUpRight, ArrowDownRight, Activity, ExternalLink, User, Thermometer } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import { MarketBrowser } from "@/components/market-browser";

interface Whale {
  username: string;
  proxyAddress: string;
  pnl: number;
  volume: number;
  rank: number;
  image?: string;
}

interface ActivityItem {
  id: string;
  title: string;
  side: string;
  amount: number;
  price: number;
  timestamp: string;
  icon?: string;
}

interface WeatherEdge {
  market: any;
  analysis: {
    modelProb: number;
    marketProb: number;
    edge: number;
    recommendation: string;
    city: string;
    type: string;
  };
}

function WhaleTab() {
  const [selectedWhale, setSelectedWhale] = useState<string | null>(null);

  const { data: leaderboard, isLoading: loadingLeaderboard } = useQuery<Whale[]>({
    queryKey: ["/api/whales/leaderboard"],
    queryFn: async () => {
      const res = await fetch("/api/whales/leaderboard");
      if (!res.ok) throw new Error("Failed to fetch leaderboard");
      return res.json();
    },
    refetchInterval: 60000,
  });

  const { data: activity, isLoading: loadingActivity } = useQuery<ActivityItem[]>({
    queryKey: ["/api/whales/activity", selectedWhale],
    queryFn: async () => {
      if (!selectedWhale) return [];
      const res = await fetch(`/api/whales/activity?address=${selectedWhale}`);
      if (!res.ok) throw new Error("Failed to fetch activity");
      return res.json();
    },
    enabled: !!selectedWhale,
  });

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(val);

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-2 border border-border/50 bg-card/80">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-emerald-500" />
            Top Traders by PNL
          </CardTitle>
          <CardDescription>Ranked by all-time profit on Polymarket.</CardDescription>
        </CardHeader>
        <CardContent>
          {loadingLeaderboard ? (
            <div className="space-y-2">
              {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12 text-center">#</TableHead>
                  <TableHead>Trader</TableHead>
                  <TableHead className="text-right">PNL</TableHead>
                  <TableHead className="text-right">Volume</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leaderboard?.map((whale) => (
                  <TableRow
                    key={whale.proxyAddress}
                    className={`cursor-pointer transition-colors hover:bg-muted/50 ${selectedWhale === whale.proxyAddress ? "bg-muted" : ""}`}
                    onClick={() => setSelectedWhale(whale.proxyAddress)}
                  >
                    <TableCell className="font-mono text-center font-bold text-muted-foreground">{whale.rank}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Avatar className="h-7 w-7 border border-border/50">
                          <AvatarImage src={whale.image} />
                          <AvatarFallback><User className="h-3.5 w-3.5" /></AvatarFallback>
                        </Avatar>
                        <div>
                          <p className="font-medium text-sm truncate max-w-[140px]">{whale.username || "Anonymous"}</p>
                          <p className="text-[10px] text-muted-foreground font-mono">
                            {whale.proxyAddress ? `${whale.proxyAddress.slice(0, 6)}…${whale.proxyAddress.slice(-4)}` : "—"}
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-mono font-bold text-emerald-500">{formatCurrency(whale.pnl)}</TableCell>
                    <TableCell className="text-right font-mono text-muted-foreground">{formatCurrency(whale.volume)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card className="border border-border/50 bg-card/80">
        <CardHeader className="border-b border-border/50">
          <CardTitle className="text-lg flex items-center gap-2">
            <Activity className="h-5 w-5 text-teal-500" />
            Live Activity
          </CardTitle>
          <CardDescription>
            {selectedWhale ? "Recent trades for selected whale" : "Click a trader to view activity"}
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {!selectedWhale ? (
            <div className="flex flex-col items-center justify-center p-10 text-center text-muted-foreground">
              <FishSymbol className="h-8 w-8 mb-3 opacity-20" />
              <p className="text-sm">Select a trader from the leaderboard</p>
            </div>
          ) : loadingActivity ? (
            <div className="p-4 space-y-3">
              {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
            </div>
          ) : (
            <ScrollArea className="h-[460px]">
              <div className="divide-y divide-border/30">
                {activity?.map((item) => (
                  <div key={item.id} className="p-3.5 hover:bg-muted/30 transition-colors">
                    <div className="flex justify-between items-center mb-1">
                      <Badge className={`text-[10px] font-bold ${item.side === "BUY" ? "bg-emerald-500/20 text-emerald-400 border-none" : "bg-red-500/20 text-red-400 border-none"}`}>
                        {item.side}
                      </Badge>
                      <span className="text-[10px] text-muted-foreground font-mono">
                        {new Date(item.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                    <p className="text-xs font-medium line-clamp-2 mb-1.5">{item.title}</p>
                    <div className="flex justify-between text-xs font-mono">
                      <span className="font-bold">{formatCurrency(item.amount)}</span>
                      <span className="text-muted-foreground">{(item.price * 100).toFixed(1)}¢</span>
                    </div>
                  </div>
                ))}
                {activity?.length === 0 && (
                  <div className="p-8 text-center text-muted-foreground text-xs italic">No recent activity found.</div>
                )}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function WeatherTab() {
  const { data: edges, isLoading } = useQuery<WeatherEdge[]>({
    queryKey: ["/api/weather/edges"],
    queryFn: async () => {
      const res = await fetch("/api/weather/edges");
      if (!res.ok) throw new Error("Failed to fetch weather edges");
      return res.json();
    },
    refetchInterval: 300000,
  });

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <Card className="border border-border/50 bg-card/80 overflow-hidden">
          <CardHeader className="border-b border-border/50">
            <CardTitle className="text-lg flex items-center gap-2">
              <CloudRain className="h-5 w-5 text-cyan-500" />
              Weather Arbitrage Markets
            </CardTitle>
            <CardDescription>Binary weather prediction markets with price misalignment.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <MarketBrowser
              onlyWeather={true}
              autoRefresh={true}
              refreshInterval="1"
              defaultInvestment={500}
            />
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        <Card className="border border-border/50 bg-card/80">
          <CardHeader className="border-b border-border/50">
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-cyan-500" />
              Directional Edge
            </CardTitle>
            <CardDescription>GFS model vs. market implied probability</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="p-8 text-center space-y-3">
                <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-cyan-500 mx-auto" />
                <p className="text-xs text-muted-foreground font-mono">Running GFS Analysis...</p>
              </div>
            ) : edges && edges.length > 0 ? (
              <ScrollArea className="h-[480px]">
                <div className="divide-y divide-border/30">
                  {edges.map((edge, idx) => (
                    <div key={idx} className="p-4 hover:bg-muted/30 transition-colors">
                      <div className="flex justify-between items-center mb-2">
                        <Badge variant="outline" className="bg-cyan-500/10 text-cyan-400 border-none text-[10px] flex items-center gap-1">
                          <Thermometer className="h-3 w-3" /> {edge.analysis.city}
                        </Badge>
                        <div className={`flex items-center font-mono font-bold text-xs ${edge.analysis.edge > 0 ? "text-emerald-500" : "text-red-500"}`}>
                          {edge.analysis.edge > 0 ? <ArrowUpRight className="h-3 w-3 mr-0.5" /> : <ArrowDownRight className="h-3 w-3 mr-0.5" />}
                          {Math.abs(edge.analysis.edge)}% Edge
                        </div>
                      </div>
                      <p className="text-xs font-medium leading-snug mb-3">{edge.market.title}</p>
                      <div className="space-y-2">
                        <div className="space-y-1">
                          <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
                            <span>Model</span>
                            <span className="text-foreground">{edge.analysis.modelProb}%</span>
                          </div>
                          <Progress value={edge.analysis.modelProb} className="h-1" />
                        </div>
                        <div className="space-y-1">
                          <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
                            <span>Market</span>
                            <span className="text-foreground">{edge.analysis.marketProb}%</span>
                          </div>
                          <Progress value={edge.analysis.marketProb} className="h-1" />
                        </div>
                      </div>
                      <Badge className={`mt-3 w-full justify-center text-[10px] font-bold tracking-wider uppercase py-0.5 ${
                        edge.analysis.recommendation === "buy_yes" ? "bg-emerald-600/80 text-white" :
                        edge.analysis.recommendation === "buy_no" ? "bg-red-600/80 text-white" :
                        "bg-muted text-muted-foreground"
                      }`}>
                        {edge.analysis.recommendation.replace("_", " ")}
                      </Badge>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            ) : (
              <div className="flex flex-col items-center justify-center p-10 text-center text-muted-foreground">
                <AlertCircle className="h-8 w-8 mb-3 opacity-20" />
                <p className="text-xs">No significant mispricings detected.</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border border-border/30 bg-muted/10">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs flex items-center gap-2 text-muted-foreground">
              <Info className="h-3.5 w-3.5" /> GFS 0.25° Data Source
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              Model output interpolated from GFS 0.25° ensemble (31-member probabilistic spread). Use Kelly Criterion for position sizing.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function MarketIntelPage() {
  return (
    <div className="container mx-auto px-4 py-6 max-w-7xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Market Intelligence</h1>
        <p className="text-sm text-muted-foreground mt-1">Whale tracking and weather market edges</p>
      </div>

      <Tabs defaultValue="whales">
        <TabsList className="mb-6">
          <TabsTrigger value="whales" className="flex items-center gap-2">
            <FishSymbol className="w-4 h-4" />
            Whale Tracker
          </TabsTrigger>
          <TabsTrigger value="weather" className="flex items-center gap-2">
            <CloudRain className="w-4 h-4" />
            Weather Edge
          </TabsTrigger>
        </TabsList>
        <TabsContent value="whales">
          <WhaleTab />
        </TabsContent>
        <TabsContent value="weather">
          <WeatherTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
