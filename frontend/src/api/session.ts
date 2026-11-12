import { http } from './client';
import type { SessionItem, ChatMessage } from '../types';

export const sessionApi = {
  list(limit = 30): Promise<{ items: SessionItem[] }> {
    return http.get(`/api/sessions?limit=${limit}`);
  },
  getMessages(id: string): Promise<{ items: ChatMessage[] }> {
    return http.get(`/api/sessions/${id}/messages`);
  },
  remove(id: string): Promise<{ deleted: boolean }> {
    return http.delete(`/api/sessions/${id}`);
  },
  removeAll(): Promise<{ deleted_count: number }> {
    return http.delete('/api/sessions');
  },
};
