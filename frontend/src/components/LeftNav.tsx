import type { ReactNode } from "react";
import CollapseToggle from "./CollapseToggle";

export type Tab =
  | "home"
  | "dashboard"
  | "executor"
  | "dag-viewer"
  | "sop-studio"
  | "settings"
  | "profile";

interface NavItem {
  key: Tab;
  label: string;
  icon: ReactNode;
  adminOnly?: boolean;
  group?: "primary" | "footer";
}

/** Per-tab sub-content rendered below the parent when the parent is
 * active and the rail is expanded. Null/undefined hides the sub-tree. */
export type SubContentMap = Partial<Record<Tab, ReactNode>>;

const NAV_ITEMS: NavItem[] = [
  {
    key: "home",
    label: "Home",
    icon: (
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 11l9-8 9 8" />
        <path d="M5 10v10h14V10" />
      </svg>
    ),
  },
  {
    key: "dashboard",
    label: "Dashboard",
    icon: (
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="9" rx="1.5" />
        <rect x="14" y="3" width="7" height="5" rx="1.5" />
        <rect x="14" y="12" width="7" height="9" rx="1.5" />
        <rect x="3" y="16" width="7" height="5" rx="1.5" />
      </svg>
    ),
  },
  {
    key: "executor",
    label: "Executor",
    icon: (
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 4v16l14-8z" />
      </svg>
    ),
  },
  {
    key: "dag-viewer",
    label: "Workflow Map",
    icon: (
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="6" cy="6" r="2.5" />
        <circle cx="18" cy="6" r="2.5" />
        <circle cx="12" cy="18" r="2.5" />
        <path d="M8 7l3 9M16 7l-3 9" />
      </svg>
    ),
  },
  {
    key: "sop-studio",
    label: "SOP Studio",
    adminOnly: true,
    icon: (
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
        <path d="M14 3v6h6" />
        <path d="M9 13h6M9 17h4" />
      </svg>
    ),
  },
  {
    key: "settings",
    label: "Settings",
    group: "footer",
    icon: (
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 0 1-4 0v-.08A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.56-1.03H3a2 2 0 0 1 0-4h.08A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H9a1.7 1.7 0 0 0 1-1.56V3a2 2 0 0 1 4 0v.08a1.7 1.7 0 0 0 1 1.56 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87V9a1.7 1.7 0 0 0 1.56 1H21a2 2 0 0 1 0 4h-.08a1.7 1.7 0 0 0-1.56 1z" />
      </svg>
    ),
  },
  {
    key: "profile",
    label: "Profile",
    group: "footer",
    icon: (
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8" />
      </svg>
    ),
  },
];

interface Props {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  isAdmin: boolean;
  collapsed: boolean;
  onToggleCollapse: () => void;
  /** Per-tab sub-content rendered inline under the parent when expanded
   * and the rail is open. Each key maps to a tab; missing keys render
   * no sub-tree. */
  subContent?: SubContentMap;
}

export default function LeftNav({
  activeTab,
  onTabChange,
  isAdmin,
  collapsed,
  onToggleCollapse,
  subContent,
}: Props) {
  const visible = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin);
  const primary = visible.filter((i) => i.group !== "footer");
  const footer = visible.filter((i) => i.group === "footer");

  return (
    <nav
      aria-label="Primary navigation"
      className="h-full flex flex-col bg-[var(--color-surface)] border-r border-[var(--color-border)] overflow-y-auto"
    >
      <div className={`flex items-center ${collapsed ? "justify-center" : "justify-end"} px-3 pt-3 pb-2`}>
        <CollapseToggle side="left" collapsed={collapsed} onToggle={onToggleCollapse} />
      </div>

      <ul className="flex-1 flex flex-col gap-1 px-2 mt-1">
        {primary.map((item) => {
          const active = activeTab === item.key;
          const sub = !collapsed && active ? subContent?.[item.key] : null;
          return (
            <li key={item.key}>
              <NavButton
                item={item}
                collapsed={collapsed}
                active={active}
                onClick={() => onTabChange(item.key)}
              />
              {sub && (
                <div className="mt-1 ml-1 mb-2 border-l border-[var(--color-border)] pl-1">
                  {sub}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      <ul className="flex flex-col gap-1 px-2 pb-3 pt-2 border-t border-[var(--color-border)]">
        {footer.map((item) => (
          <li key={item.key}>
            <NavButton
              item={item}
              collapsed={collapsed}
              active={activeTab === item.key}
              onClick={() => onTabChange(item.key)}
            />
          </li>
        ))}
      </ul>
    </nav>
  );
}

function NavButton({
  item,
  collapsed,
  active,
  onClick,
}: {
  item: NavItem;
  collapsed: boolean;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={collapsed ? item.label : undefined}
      aria-current={active ? "page" : undefined}
      className={`w-full flex items-center gap-3 ${
        collapsed ? "justify-center px-0" : "px-3"
      } py-2.5 rounded-md text-sm font-medium transition-colors ${
        active
          ? "bg-[var(--color-accent-glow)] text-[var(--color-accent)]"
          : "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text-primary)]"
      }`}
      style={collapsed ? { minHeight: 44 } : undefined}
    >
      <span className="shrink-0">{item.icon}</span>
      {!collapsed && <span className="truncate">{item.label}</span>}
    </button>
  );
}
