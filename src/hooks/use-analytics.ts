"use client";

import posthog from "posthog-js";

type ToolEventProps = {
  tool_id: string;
  tool_title: string;
  tool_category: string;
};

export function useAnalytics() {
  function trackToolClicked(props: ToolEventProps) {
    posthog.capture("tool_clicked", props);
  }

  function trackToolStarted(props: ToolEventProps) {
    posthog.capture("tool_started", props);
  }

  function trackToolCompleted(props: ToolEventProps & { duration_ms?: number }) {
    posthog.capture("tool_completed", props);
  }

  function trackToolError(props: ToolEventProps & { error?: string }) {
    posthog.capture("tool_error", props);
  }

  return { trackToolClicked, trackToolStarted, trackToolCompleted, trackToolError };
}
