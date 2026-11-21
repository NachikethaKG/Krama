"use client";

import { useId } from "react";
import { useTranslations } from "next-intl";
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

/** Name, badge and description of each option: targetPicker.option.<type> in the "approval" namespace. */
interface TargetOption {
  type: TargetType;
  color: string;
  url: string;
  testId: string;
}

const TARGET_OPTIONS: TargetOption[] = [
  {
    type: "gitea",
    color: "var(--verify)",
    url: GITEA_DEFAULT_URL,
    testId: "target-option-gitea",
  },
  {
    type: "github",
    color: "var(--run)",
    url: GITHUB_DEFAULT_URL,
    testId: "target-option-github",
  },
  {
    type: "custom",
    color: "var(--approve)",
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
  const t = useTranslations("approval");
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
      : { valid: true, error: undefined, errorKey: undefined };

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
          className="text-xs font-bold uppercase tracking-wider text-plan"
        >
          {t("targetPicker.label")}
        </label>
        <p className="text-xs text-ink-400">
          {t("targetPicker.hint")}
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
              className={`flex flex-col items-start rounded-2xl border p-3.5 text-left transition-all ${
                isSelected ? "bg-white/[0.07]" : "border-white/10 bg-white/[0.03] hover:border-white/25"
              } ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}
              style={
                isSelected
                  ? { borderColor: opt.color, boxShadow: `0 0 0 1px ${opt.color}, 0 10px 30px -12px ${opt.color}` }
                  : undefined
              }
            >
              <div className="flex w-full items-center justify-between gap-2">
                <span className="text-sm font-bold text-white">
                  {t(`targetPicker.option.${opt.type}.name`)}
                </span>
                <span
                  className="rounded-full px-2 py-0.5 text-[10px] font-extrabold"
                  style={
                    isSelected
                      ? { background: opt.color, color: "var(--ink-950)" }
                      : { color: opt.color, background: "rgb(var(--fg-rgb) / 0.06)" }
                  }
                >
                  {t(`targetPicker.option.${opt.type}.badge`)}
                </span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-ink-300">
                {t(`targetPicker.option.${opt.type}.description`)}
              </p>
              {opt.url && (
                <span className="mt-2 font-mono text-[11px] text-ink-400">
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
            ? "kr-approve kr-tone-card mt-1 flex flex-col gap-1.5 rounded-2xl p-3.5"
            : "hidden"
        }
      >
        <label
          htmlFor={customInputId}
          className="text-xs font-bold text-approve"
        >
          {t("targetPicker.customLabel")}
        </label>
        <input
          id={customInputId}
          data-testid="custom-target-url-input"
          name="custom_target_url"
          type="url"
          value={activeCustomUrl}
          onChange={handleCustomUrlChange}
          placeholder={t("targetPicker.customPlaceholder")}
          disabled={disabled}
          required={activeTarget === "custom"}
          className="kr-input w-full px-3.5 py-2 font-mono text-sm"
        />
        {activeTarget === "custom" && validation.errorKey && (
          <p
            role="alert"
            data-testid="target-url-error"
            className="text-xs font-bold text-danger"
          >
            {t(`targetPicker.urlError.${validation.errorKey}`)}
          </p>
        )}
      </div>
    </div>
  );
}
