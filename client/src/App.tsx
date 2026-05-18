import { Switch, Route } from "wouter";
import { useState, useEffect } from "react";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ComparisonProvider } from "@/contexts/comparison-context";
import { OutcomeComparisonDock } from "@/components/outcome-comparison-dock";
import { WifiOff, Menu } from "lucide-react";
import NotFound from "@/pages/not-found";
import ArbitrageCalculator from "@/pages/arbitrage-calculator";
import HistoryPage from "@/pages/history";
import SentinelPage from "@/pages/sentinel";
import WeatherTerminalPage from "@/pages/weather";
import WhaleTrackerPage from "@/pages/whales";
import AnalysisPage from "@/pages/analysis";

import { AppSidebar } from "@/components/app-sidebar";
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";

function Router() {
  return (
    <Switch>
      <Route path="/" component={ArbitrageCalculator} />
      <Route path="/history" component={HistoryPage} />
      <Route path="/sentinel" component={SentinelPage} />
      <Route path="/weather" component={WeatherTerminalPage} />
      <Route path="/whales" component={WhaleTrackerPage} />
      <Route path="/analysis" component={AnalysisPage} />
      <Route component={NotFound} />
    </Switch>
  );
}

function OfflineIndicator() {
  const [isOffline, setIsOffline] = useState(typeof navigator !== 'undefined' ? !navigator.onLine : false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  if (!isOffline) return null;

  return (
    <div 
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 bg-destructive text-destructive-foreground px-4 py-2 rounded-full shadow-lg flex items-center gap-2 text-sm font-medium"
      data-testid="indicator-offline"
    >
      <WifiOff className="w-4 h-4" />
      Offline Mode
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ComparisonProvider>
        <TooltipProvider>
          <SidebarProvider defaultOpen={true}>
            <AppSidebar />
            <SidebarInset className="bg-background flex flex-col h-screen">
              <header className="flex h-14 shrink-0 items-center justify-between gap-2 border-b bg-background px-4">
                <div className="flex items-center gap-2">
                  <SidebarTrigger className="-ml-1" />
                  <Separator orientation="vertical" className="mr-2 h-4 hidden md:block" />
                  <div className="font-semibold text-sm md:text-base hidden sm:block">Arb Finder Terminal</div>
                </div>
              </header>
              <div className="flex-1 overflow-auto pb-24">
                <Router />
              </div>
            </SidebarInset>
          </SidebarProvider>
          <OutcomeComparisonDock />
          <OfflineIndicator />
          <Toaster />
        </TooltipProvider>
      </ComparisonProvider>
    </QueryClientProvider>
  );
}

export default App;
