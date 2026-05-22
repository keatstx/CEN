import { useEffect, useState } from "react";
import type { ReadyResponse } from "./types";
import { fetchReady, type ConciergeAction } from "./api";
import { useCurrentUser } from "./hooks/useCurrentUser";
import { useLayoutCollapse } from "./hooks/useLayoutCollapse";
import { useCaseSession } from "./hooks/useCaseSession";
import { useSOPSession } from "./hooks/useSOPSession";
import Layout from "./components/Layout";
import LeftNav, { type Tab, type SubContentMap } from "./components/LeftNav";
import Dashboard from "./components/Dashboard";
import Executor from "./components/Executor";
import DAGViewer from "./components/DAGViewer";
import SOPStudio from "./components/SOPStudio";
import Concierge from "./components/Concierge";
import Settings from "./components/Settings";
import Profile from "./components/Profile";
import WelcomeScreen from "./components/WelcomeScreen";
import ExecutorSubNav from "./components/nav/ExecutorSubNav";
import WorkflowMapSubNav from "./components/nav/WorkflowMapSubNav";
import SOPStudioSubNav from "./components/nav/SOPStudioSubNav";

export default function App() {
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("home");
  const [dagSelectedModule, setDagSelectedModule] = useState("");
  const [dashboardRefreshKey, setDashboardRefreshKey] = useState(0);

  const { user, loading: userLoading } = useCurrentUser();
  const isAdmin = user?.is_admin ?? false;

  const {
    leftCollapsed,
    rightCollapsed,
    toggleLeft,
    toggleRight,
  } = useLayoutCollapse();

  // App-level case-management state: shared between LeftNav (sub-nav
  // selectors) and Executor (center activity). Lifting it here lets
  // the concierge dispatch actions like "open case X" without
  // prop-drilling through three layers.
  const caseSession = useCaseSession();
  const sopSession = useSOPSession();

  const refreshReady = () => {
    fetchReady()
      .then(setReady)
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    refreshReady();
  }, []);

  const handleTabChange = (key: Tab) => {
    if (key === "sop-studio" && !isAdmin) return;
    setActiveTab(key);
    if (key === "dashboard") {
      setDashboardRefreshKey((k) => k + 1);
    }
  };

  const handleCaseSelectedFromDashboard = (caseId: string) => {
    caseSession.setSelectedCaseId(caseId);
    setActiveTab("executor");
  };

  const handleResetLayout = () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("cen:left-collapsed");
      window.localStorage.removeItem("cen:right-collapsed");
      window.location.reload();
    }
  };

  // Concierge action dispatcher — runs the navigation/state change
  // when the user clicks an action button under an assistant turn.
  // Keeps the activity panel in sync with what the AI just suggested.
  const handleConciergeAction = (action: ConciergeAction) => {
    switch (action.kind) {
      case "open_dashboard":
        setActiveTab("dashboard");
        setDashboardRefreshKey((k) => k + 1);
        break;
      case "open_case": {
        const caseId = action.payload?.case_id as string | undefined;
        if (caseId) {
          caseSession.setSelectedCaseId(caseId);
          setActiveTab("executor");
        }
        break;
      }
      case "start_workflow": {
        const moduleName = action.payload?.module_name as string | undefined;
        if (moduleName) {
          caseSession.setSelectedModule(moduleName);
          setActiveTab("executor");
          // Auto-start a case under the selected module + current project.
          caseSession.handleNewCase();
        }
        break;
      }
      case "switch_tab": {
        const tab = action.payload?.tab as Tab | undefined;
        if (tab) setActiveTab(tab);
        break;
      }
    }
  };

  // Sub-nav content map: LeftNav renders the right sub-tree under
  // each parent when the parent is active and the rail is expanded.
  const subContent: SubContentMap = {
    executor: (
      <ExecutorSubNav
        session={caseSession}
        modules={ready?.modules_loaded ?? []}
        onCaseOpened={() => setActiveTab("executor")}
      />
    ),
    "dag-viewer": (
      <WorkflowMapSubNav
        modules={ready?.modules_loaded ?? []}
        selectedModule={dagSelectedModule}
        onChange={(m) => {
          setDagSelectedModule(m);
          setActiveTab("dag-viewer");
        }}
      />
    ),
    "sop-studio": isAdmin ? (
      <SOPStudioSubNav
        session={sopSession}
        onSelect={() => setActiveTab("sop-studio")}
      />
    ) : null,
  };

  const leftRail = (
    <LeftNav
      activeTab={activeTab}
      onTabChange={handleTabChange}
      isAdmin={isAdmin}
      collapsed={leftCollapsed}
      onToggleCollapse={toggleLeft}
      subContent={subContent}
    />
  );

  const rightRail = (
    <Concierge
      caseRecord={caseSession.activeCase}
      onAction={handleConciergeAction}
    />
  );

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

      {activeTab === "executor" && <Executor session={caseSession} />}

      {activeTab === "dag-viewer" && (
        <DAGViewer selectedModule={dagSelectedModule} />
      )}

      {activeTab === "sop-studio" && isAdmin && (
        <SOPStudio session={sopSession} onModulePromoted={refreshReady} />
      )}

      {activeTab === "settings" && <Settings onResetLayout={handleResetLayout} />}

      {activeTab === "profile" && <Profile user={user} loading={userLoading} />}
    </Layout>
  );
}
