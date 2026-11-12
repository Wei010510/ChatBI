import { http } from './client';
import type { ReportListItem, ReportDetail } from '../types';

export interface CreateReportParams {
  message_id: string;
  name: string;
  chart_type?: string;
  overwrite?: boolean;
}

export const reportApi = {
  create(params: CreateReportParams): Promise<{ id: string; name: string }> {
    return http.post('/api/reports', params);
  },
  list(page = 1, size = 20): Promise<{ items: ReportListItem[]; total: number }> {
    return http.get(`/api/reports?page=${page}&size=${size}`);
  },
  get(id: string): Promise<ReportDetail> {
    return http.get(`/api/reports/${id}`);
  },
  rename(id: string, name: string): Promise<{ id: string; name: string }> {
    return http.patch(`/api/reports/${id}`, { name });
  },
  remove(id: string): Promise<{ deleted: boolean }> {
    return http.delete(`/api/reports/${id}`);
  },
};
