import { create } from 'zustand';
import type { ReportListItem } from '../types';
import { reportApi } from '../api/report';
import { handleApiError } from '../api/client';

interface ReportState {
  list: ReportListItem[];
  total: number;
  loading: boolean;

  fetchList: (page?: number, size?: number) => Promise<void>;
  remove: (id: string) => Promise<boolean>;
  rename: (id: string, name: string) => Promise<boolean>;
}

export const useReportStore = create<ReportState>((set, get) => ({
  list: [],
  total: 0,
  loading: false,

  fetchList: async (page = 1, size = 20) => {
    set({ loading: true });
    try {
      const resp = await reportApi.list(page, size);
      set({ list: resp.items, total: resp.total, loading: false });
    } catch (e) {
      handleApiError(e);
      set({ loading: false });
    }
  },

  remove: async (id: string) => {
    const prev = get().list;
    // 乐观更新
    set((s) => ({ list: s.list.filter((r) => r.id !== id) }));
    try {
      await reportApi.remove(id);
      return true;
    } catch (e) {
      handleApiError(e);
      // 回滚
      set({ list: prev });
      return false;
    }
  },

  rename: async (id: string, name: string) => {
    const prev = get().list;
    set((s) => ({
      list: s.list.map((r) => (r.id === id ? { ...r, name } : r)),
    }));
    try {
      await reportApi.rename(id, name);
      return true;
    } catch (e) {
      handleApiError(e);
      set({ list: prev });
      return false;
    }
  },
}));
