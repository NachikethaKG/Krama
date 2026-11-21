"use client";

import React from "react";
import { useTranslations } from "next-intl";
import type { ReviewFilterCategory } from "@/types/review";

export interface ReviewQueueCounts {
  all: number;
  outdated: number;
  heal_pending: number;
  unstable: number;
  cant_check: number;
}

export interface ReviewQueueFilterTabsProps {
  selectedCategory: ReviewFilterCategory;
  onSelectCategory: (category: ReviewFilterCategory) => void;
  counts: ReviewQueueCounts;
  className?: string;
}

interface TabDef {
  key: ReviewFilterCategory;
  /** Key under "reviews.tabs". */
  labelKey: string;
  testId: string;
  color: string;
}

const TABS: TabDef[] = [
  { key: "all", labelKey: "all", testId: "filter-tab-all", color: "var(--learn)" },
  { key: "outdated", labelKey: "outdated", testId: "filter-tab-outdated", color: "var(--plan)" },
  { key: "heal_pending", labelKey: "healPending", testId: "filter-tab-heal_pending", color: "#a855f7" },
  { key: "unstable", labelKey: "unstable", testId: "filter-tab-unstable", color: "#f97316" },
  { key: "cant_check", labelKey: "cantCheck", testId: "filter-tab-cant_check", color: "#f43f5e" },
];

export function ReviewQueueFilterTabs({
  selectedCategory,
  onSelectCategory,
  counts,
  className = "",
}: ReviewQueueFilterTabsProps) {
  const t = useTranslations("reviews");
  return (
    <div
      role="tablist"
      aria-label={t("tabs.label")}
      className={`kr-glass flex flex-wrap items-center gap-1.5 rounded-full p-1.5 ${className}`}
    >
      {TABS.map((tab) => {
        const isSelected = selectedCategory === tab.key;
        const count = counts[tab.key];

        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            data-testid={tab.testId}
            aria-selected={isSelected}
            onClick={() => onSelectCategory(tab.key)}
            className={`flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-bold transition-all ${
              isSelected ? "text-oncolor shadow-md" : "text-ink-300 hover:text-white"
            }`}
            style={
              isSelected
                ? { background: tab.color, boxShadow: `0 0 20px -4px ${tab.color}` }
                : undefined
            }
          >
            {!isSelected && (
              <span
                aria-hidden="true"
                className="size-1.5 rounded-full"
                style={{ background: tab.color }}
              />
            )}
            <span>{t(`tabs.${tab.labelKey}`)}</span>
            <span
              className={`rounded-full px-1.5 py-0.2 text-[10px] font-extrabold ${
                isSelected ? "bg-ink-950/30 text-oncolor" : "bg-white/10 text-ink-300"
              }`}
            >
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
