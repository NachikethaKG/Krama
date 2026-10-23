"use client";

import { useId } from "react";
import {
  GITEA_DEFAULT_URL,
  GITHUB_DEFAULT_URL,
  type TargetConfig,
  type TargetType,
  useTargetSelection,
  validateTargetUrl,
} from "./useTargetSelection";

export interface TargetPickerProps {
  value?: TargetType;
  customUrl?: string;
  onChange?: (config: TargetConfig, isValid: boolean) => void;
  disabled?: boolean;
  className?: string;
}

interface TargetOption {
  type: TargetType;
  name: string;
  badge: string;
  description: string;
  url: string;
  testId: string;
}

const TARGET_OPTIONS: TargetOption[] = [
  {
    type: "gitea",
    name: "Gitea (Local)",
    badge: "Local",
    description: "Sandbox repository instance for offline testing",
    url: GITEA_DEFAULT_URL,
    testId: "target-option-gitea",
  },
  {
    type: "github",
    name: "GitHub (Real)",
    badge: "Live",
    description: "github.com repository (uses encrypted browser session)",
    url: GITHUB_DEFAULT_URL,
    testId: "target-option-github",
  },
  {
    type: "custom",
    name: "Custom Target",
    badge: "Custom",
    description: "Arbitrary Git server or enterprise web endpoint",
    url: "",
    testId: "target-option-custom",
  },
];

export function TargetPicker({
  value,
  customUrl: externalCustomUrl,
  onChange,
  disabled = false,
  className = "",
}: TargetPickerProps) {
  const customInputId = useId();
  const isControlled = value !== undefined;

  // Internal uncontrolled hook fallback
  const internalSelection = useTargetSelection({
    initialTarget: value,
    initialCustomUrl: externalCustomUrl,
    onTargetChange: isControlled ? undefined : onChange,
  });
  const activeTarget: TargetType = isControlled ? value : internalSelection.targetType;
  const activeCustomUrl: string = isControlled
    ? (externalCustomUrl ?? "")
    : internalSelection.customUrl;

  const validation =
    activeTarget === "custom"
      ? validateTargetUrl(activeCustomUrl)
      : { valid: true, error: undefined };

  const handleSelect = (type: TargetType) => {
    if (disabled) return;
    if (isControlled) {
      if (type === "gitea") {
        onChange?.({ type: "gitea", url: GITEA_DEFAULT_URL }, true);
      } else if (type === "github") {
        onChange?.({ type: "github", url: GITHUB_DEFAULT_URL }, true);
      } else {
        const v = validateTargetUrl(activeCustomUrl);
        onChange?.({ type: "custom", url: activeCustomUrl }, v.valid);
      }
    } else {
      internalSelection.selectTarget(type);
    }
  };

  const handleCustomUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (disabled) return;
    const nextVal = e.target.value;
    if (isControlled) {
      const v = validateTargetUrl(nextVal);
      onChange?.({ type: "custom", url: nextVal }, v.valid);
    } else {
      internalSelection.setCustomUrl(nextVal);
    }
  };

  return (
    <div className={`flex flex-col gap-3 ${className}`} data-testid="target-picker">
      <div className="flex flex-col gap-1">
        <label
          id="target-picker-label"
          className="text-xs font-semibold uppercase tracking-wider text-zinc-600 dark:text-zinc-400"
        >
          Target Environment
        </label>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          Choose where the workflow agent executes tasks.
        </p>
      </div>

      <div
        role="radiogroup"
        aria-labelledby="target-picker-label"
        className="grid grid-cols-1 gap-2.5 sm:grid-cols-3"
      >
        {TARGET_OPTIONS.map((opt) => {
          const isSelected = activeTarget === opt.type;
          return (
            <button
              key={opt.type}
              type="button"
              role="radio"
              aria-checked={isSelected}
              data-testid={opt.testId}
              disabled={disabled}
              onClick={() => handleSelect(opt.type)}
              className={`flex flex-col items-start rounded-xl border p-3.5 text-left transition-all ${
                isSelected
                  ? "border-indigo-600 bg-indigo-50/40 ring-2 ring-indigo-500/20 dark:border-indigo-500 dark:bg-indigo-950/20"
                  : "border-zinc-200 bg-white hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700"
              } ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}
            >
              <div className="flex w-full items-center justify-between gap-2">
                <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  {opt.name}
                </span>
                <span
                  className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium ${
                    isSelected
                      ? "bg-indigo-600 text-white dark:bg-indigo-500"
                      : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                  }`}
                >
                  {opt.badge}
                </span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-zinc-500 dark:text-zinc-400">
                {opt.description}
              </p>
              {opt.url && (
                <span className="mt-2 text-[11px] font-mono text-zinc-400 dark:text-zinc-500">
                  {opt.url}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Custom target URL input: unhidden when activeTarget === "custom" */}
      <div
        data-testid="custom-target-section"
        className={
          activeTarget === "custom"
            ? "mt-1 flex flex-col gap-1.5 rounded-xl border border-zinc-200 bg-zinc-50/50 p-3.5 dark:border-zinc-800 dark:bg-zinc-900/50"
            : "hidden"
        }
      >
        <label
          htmlFor={customInputId}
          className="text-xs font-semibold text-zinc-700 dark:text-zinc-300"
        >
          Custom Target Base URL
        </label>
        <input
          id={customInputId}
          data-testid="custom-target-url-input"
          name="custom_target_url"
          type="url"
          value={activeCustomUrl}
          onChange={handleCustomUrlChange}
          placeholder="https://git.example.corp"
          disabled={disabled}
          required={activeTarget === "custom"}
          className="w-full rounded-lg border border-zinc-300 bg-white px-3.5 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-indigo-500 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
        {activeTarget === "custom" && validation.error && (
          <p
            role="alert"
            data-testid="target-url-error"
            className="text-xs font-medium text-rose-600 dark:text-rose-400"
          >
            {validation.error}
          </p>
        )}
      </div>
    </div>
  );
}
