// --- API request/response types matching backend models ---

export interface HealthResponse {
  status: string;
}

export interface ReadyResponse {
  status: string;
  modules_loaded: string[];
  llm_backend: string;
  llm_available: boolean;
}

export interface WorkflowInput {
  module_name: string;
  context: Record<string, unknown>;
}

export interface WorkflowResult {
  module_name: string;
  executed_nodes: string[];
  final_outcome: string;
  context: Record<string, unknown>;
}

export interface LLMGenerateRequest {
  prompt: string;
  max_tokens?: number;
}

export interface LLMGenerateResponse {
  response: string;
  backend: string;
}

// --- Module field configuration ---

export interface FieldConfig {
  key: string;
  label: string;
  type: "number" | "text" | "boolean" | "select";
  required?: boolean;
  options?: { value: string; label: string }[];
}

export interface ModuleConfig {
  label: string;
  description: string;
  fields: FieldConfig[];
}

export const MODULE_CONFIGS: Record<string, ModuleConfig> = {
  charity_care_navigator: {
    label: "Charity Care Navigator",
    description:
      "Determines charity care eligibility based on income as a percentage of the Federal Poverty Level and auto-submits applications.",
    fields: [
      {
        key: "income_fpl_percent",
        label: "Income (% of FPL)",
        type: "number",
        required: true,
      },
    ],
  },
  debt_cancellation_engine: {
    label: "Debt Cancellation Engine",
    description:
      "Audits medical bills for duplicate charges and No Surprises Act violations, then generates dispute letters.",
    fields: [
      {
        key: "bill_summary",
        label: "Bill Summary",
        type: "text",
        required: true,
      },
      {
        key: "violations_count",
        label: "Violations Count",
        type: "number",
        required: true,
      },
    ],
  },
  insurance_appeal_assistant: {
    label: "Insurance Appeal Assistant",
    description:
      "Classifies insurance claim denials and generates tailored appeal letters based on denial type.",
    fields: [
      {
        key: "denial_reason",
        label: "Denial Reason",
        type: "text",
        required: true,
      },
      {
        key: "denial_type",
        label: "Denial Type",
        type: "select",
        required: true,
        options: [
          { value: "medical_necessity", label: "Medical Necessity" },
          { value: "coding_error", label: "Coding Error" },
          { value: "other", label: "Other" },
        ],
      },
    ],
  },
  benefits_enrollment_navigator: {
    label: "Benefits Enrollment Navigator",
    description:
      "Cascading eligibility check for Medicaid, ACA subsidies, and CHIP based on household income and family status.",
    fields: [
      {
        key: "income_fpl_percent",
        label: "Income (% of FPL)",
        type: "number",
        required: true,
      },
      {
        key: "has_children_under_19",
        label: "Has children under 19?",
        type: "boolean",
      },
    ],
  },
  community_resource_router: {
    label: "Community Resource Router",
    description:
      "Screens for housing, food, and transportation needs and routes to local community resources.",
    fields: [
      { key: "needs_housing", label: "Needs housing assistance?", type: "boolean" },
      { key: "needs_food", label: "Needs food assistance?", type: "boolean" },
      { key: "needs_transport", label: "Needs transportation?", type: "boolean" },
      { key: "zip_code", label: "ZIP Code", type: "text", required: true },
    ],
  },
};
