"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type TargetType = "gitea" | "github" | "custom";

export interface TargetConfig {
  type: TargetType;
  url: string;
}

export const GITEA_DEFAULT_URL =
  process.env.NEXT_PUBLIC_GITEA_URL || "http://localhost:3000";
export const GITHUB_DEFAULT_URL = "https://github.com";

const STORAGE_KEY = "krama:target_config";

export interface UrlValidationResult {
  valid: boolean;
  error?: string;
}

/**
 * Validates a target URL: must have http:// or https:// protocol and a valid host.
 */
export function validateTargetUrl(url: string): UrlValidationResult {
  const trimmed = url.trim();
  if (!trimmed) {
    return { valid: false, error: "Target URL is required." };
  }
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return {
        valid: false,
        error: "URL must use http:// or https:// protocol (e.g. https://github.example.com).",
      };
    }
    if (!parsed.hostname) {
      return { valid: false, error: "URL must include a valid host name." };
    }
    return { valid: true };
  } catch {
    return {
      valid: false,
      error: "Please enter a valid URL (e.g. https://github.example.com).",
    };
  }
}

export interface UseTargetSelectionOptions {
  initialTarget?: TargetType;
  initialCustomUrl?: string;
  onTargetChange?: (config: TargetConfig, isValid: boolean) => void;
  persistKey?: string;
}

export interface UseTargetSelectionReturn {
  targetType: TargetType;
  targetUrl: string;
  customUrl: string;
  isValid: boolean;
  validationError: string | null;
  selectTarget: (type: TargetType) => void;
  setCustomUrl: (url: string) => void;
  config: TargetConfig;
}

export function useTargetSelection({
  initialTarget,
  initialCustomUrl = "",
  onTargetChange,
  persistKey = STORAGE_KEY,
}: UseTargetSelectionOptions = {}): UseTargetSelectionReturn {
  const [targetType, setTargetType] = useState<TargetType>(() => {
    if (initialTarget) return initialTarget;
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem(persistKey);
        if (stored) {
          const parsed = JSON.parse(stored) as Partial<TargetConfig>;
          if (parsed.type && ["gitea", "github", "custom"].includes(parsed.type)) {
            return parsed.type as TargetType;
          }
        }
      } catch {
        // Fall back to default on parse/storage error
      }
    }
    return "gitea";
  });

  const [customUrl, setCustomUrlState] = useState<string>(() => {
    if (initialCustomUrl) return initialCustomUrl;
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem(persistKey);
        if (stored) {
          const parsed = JSON.parse(stored) as Partial<TargetConfig>;
          if (parsed.url && parsed.type === "custom") {
            return parsed.url;
          }
        }
      } catch {
        // Ignore storage error
      }
    }
    return "";
  });

  // Determine current active target URL
  let targetUrl = GITEA_DEFAULT_URL;
  let isValid = true;
  let validationError: string | null = null;

  if (targetType === "gitea") {
    targetUrl = GITEA_DEFAULT_URL;
    isValid = true;
  } else if (targetType === "github") {
    targetUrl = GITHUB_DEFAULT_URL;
    isValid = true;
  } else if (targetType === "custom") {
    targetUrl = customUrl.trim();
    const validation = validateTargetUrl(customUrl);
    isValid = validation.valid;
    validationError = validation.error ?? null;
  }

  // Persist selection whenever it changes
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem(
        persistKey,
        JSON.stringify({
          type: targetType,
          url: targetType === "custom" ? customUrl : targetUrl,
        }),
      );
    } catch {
      // Ignore localStorage quotas or security errors
    }
  }, [targetType, targetUrl, customUrl, persistKey]);

  const isFirstRender = useRef(true);

  // Notify listener on change after initial mount
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    onTargetChange?.({ type: targetType, url: targetUrl }, isValid);
  }, [targetType, targetUrl, isValid, onTargetChange]);

  const selectTarget = useCallback((type: TargetType) => {
    setTargetType(type);
  }, []);

  const setCustomUrl = useCallback((url: string) => {
    setCustomUrlState(url);
  }, []);

  return {
    targetType,
    targetUrl,
    customUrl,
    isValid,
    validationError,
    selectTarget,
    setCustomUrl,
    config: {
      type: targetType,
      url: targetUrl,
    },
  };
}
