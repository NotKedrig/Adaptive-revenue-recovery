import { useCallback, useEffect, useState } from "react";
import { ApiError, advanceRecovery, getCase, getCaseTimeline, getMetrics, getQueue, getRecovered, loadDemoData } from "../services/api";
import type { Metrics, QueueItem, TimelineEvent } from "../types/recovery";

interface ToastState {
  title: string;
  body?: string;
}

export function useRecoveryConsole() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [recovered, setRecovered] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<QueueItem | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const refreshLists = useCallback(async () => {
    const [nextMetrics, nextQueue, nextRecovered] = await Promise.all([
      getMetrics(),
      getQueue(),
      getRecovered(),
    ]);
    setMetrics(nextMetrics);
    setQueue(nextQueue);
    setRecovered(nextRecovered);
    setUnavailable(false);
    setLastUpdated(
      new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    );
    return { nextQueue, nextRecovered };
  }, []);

  const refreshCase = useCallback(async (caseId: string) => {
    setTimelineLoading(true);
    try {
      const [detail, timeline] = await Promise.all([getCase(caseId), getCaseTimeline(caseId)]);
      setSelected(detail);
      setEvents(timeline);
      setActionError(null);
    } catch (error) {
      setActionError(
        error instanceof ApiError ? error.message : "Unable to load this recovery case.",
      );
    } finally {
      setTimelineLoading(false);
    }
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const lists = await refreshLists();
      const empty = lists.nextQueue.length === 0 && lists.nextRecovered.length === 0;
      if (empty) {
        setDemoLoading(true);
        await loadDemoData();
        await refreshLists();
        setToast({
          title: "Demo data loaded",
          body: "3 recovery scenarios ready",
        });
      }
    } catch {
      setUnavailable(true);
    } finally {
      setLoading(false);
      setDemoLoading(false);
    }
  }, [refreshLists]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (!selectedId) {
      setSelected(null);
      setEvents([]);
      return;
    }
    void refreshCase(selectedId);
  }, [refreshCase, selectedId]);

  const openCase = useCallback((caseId: string) => setSelectedId(caseId), []);
  const closeCase = useCallback(() => {
    setSelectedId(null);
    setActionError(null);
  }, []);

  const advance = useCallback(async () => {
    if (!selectedId || advancing) return;
    setAdvancing(true);
    setActionError(null);
    try {
      await advanceRecovery(selectedId);
      await Promise.all([refreshLists(), refreshCase(selectedId)]);
    } catch (error) {
      setActionError(
        error instanceof ApiError ? error.message : "Could not advance recovery.",
      );
    } finally {
      setAdvancing(false);
    }
  }, [selectedId, advancing, refreshLists, refreshCase]);

  const resetDemo = useCallback(async () => {
    setDemoLoading(true);
    try {
      await loadDemoData();
      setSelectedId(null);
      await refreshLists();
      setToast({
        title: "Demo data loaded",
        body: "3 recovery scenarios ready",
      });
    } catch {
      setUnavailable(true);
    } finally {
      setDemoLoading(false);
    }
  }, [refreshLists]);

  const dismissToast = useCallback(() => setToast(null), []);

  return {
    metrics,
    queue,
    recovered,
    loading,
    unavailable,
    selected,
    events,
    timelineLoading,
    advancing,
    actionError,
    demoLoading,
    toast,
    lastUpdated,
    selectedId,
    openCase,
    closeCase,
    advance,
    resetDemo,
    dismissToast,
  };
}
