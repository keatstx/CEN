import { useEffect, useState } from "react";
import type { ReadyResponse, Session } from "./types";
import { fetchReady } from "./api";
import { useCurrentUser } from "./hooks/useCurrentUser";
import { useLayoutCollapse } from "./hooks/useLayoutCollapse";
import Layout from "./components/Layout";
import LeftNav, { type Tab } from "./components/LeftNav";
import Dashboard from "./components/Dashboard";
import Executor from "./components/Executor";
import DAGViewer from "./components/DAGViewer";
import SOPStudio from "./components/SOPStudio";
import Concierge from "./components/Concierge";
import Settings from "./components/Settings";
import Profile from "./components/Profile";
import WelcomeScreen from "./components/WelcomeScreen";

export default function App() {
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("home");
  const [dagSelectedModule, setDagSelectedModule] = useState("");
  const [activeCase, setActiveCase] = useState<Session | null>(null);
  const [executorPreselect, setExecutorPreselect] = useState<string | null>(null);
  const [dashboardRefreshKey, setDashboardRefreshKey] = useState(0);

  const { user, loading: userLoading } = useCurrentUser();
  const isAdmin = user?.is_admin ?? false;

  const {
    leftCollapsed,
    rightCollapsed,
    toggleLeft,
    toggleRight,
  } = useLayoutCollapse();

  const refreshReady = () => {
    fetchReady()
      .then(setReady)
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    refreshReady();
  }, []);

  const handleTabChange = (key: Tab) => {
    // Block admin-only tabs from being activated when not admin (defense
    // in depth — LeftNav already hides the entry).
    if (key === "sop-studio" && !isAdmin) return;
    setActiveTab(key);
    if (key === "dashboard") {
      setDashboardRefreshKey((k) => k + 1);
    }
  };

  const handleCaseSelectedFromDashboard = (caseId: string) => {
    setExecutorPreselect(caseId);
    setActiveTab("executor");
  };

  const handleResetLayout = () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("cen:left-collapsed");
      window.localStorage.removeItem("cen:right-collapsed");
      window.location.reload();
    }
  };

  const leftRail = (
    <LeftNav
      activeTab={activeTab}
      onTabChange={handleTabChange}
      isAdmin={isAdmin}
      collapsed={leftCollapsed}
      onToggleCollapse={toggleLeft}
    />
  );

  const rightRail = <Concierge caseRecord={activeCase} />;

  return (
    <Layout
      ready={ready}
      error={error}
      leftRail={leftRail}
      rightRail={rightRail}
      leftCollapsed={leftCollapsed}
      rightCollapsed={rightCollapsed}
      onToggleRight={toggleRight}
    >
      {activeTab === "home" && (
        <WelcomeScreen
          onContinue={() => setActiveTab("dashboard")}
          onStart={() => setActiveTab("executor")}
        />
      )}

      {activeTab === "dashboard" && (
        <Dashboard
          onCaseSelected={handleCaseSelectedFromDashboard}
          refreshKey={dashboardRefreshKey}
        />
      )}

      {activeTab === "executor" && (
        <Executor
          modules={ready?.modules_loaded ?? []}
          initialCaseId={executorPreselect}
          onActiveCaseChange={setActiveCase}
        />
      )}

      {activeTab === "dag-viewer" && (
        <DAGViewer
          modules={ready?.modules_loaded ?? []}
          selectedModule={dagSelectedModule}
          onModuleChange={setDagSelectedModule}
        />
      )}

      {activeTab === "sop-studio" && isAdmin && (
        <SOPStudio onModulePromoted={refreshReady} />
      )}

      {activeTab === "settings" && <Settings onResetLayout={handleResetLayout} />}

      {activeTab === "profile" && <Profile user={user} loading={userLoading} />}
    </Layout>
  );
}

