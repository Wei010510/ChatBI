import { http } from './client';
import type { ChatAnswer } from '../types';

export interface AskParams {
  session_id?: string;
  question: string;
}

export interface ClarifyParams {
  session_id: string;
  clarify_id: string;
  answer: { value?: string; text?: string };
}

// 问答链路要串行跑多次模型调用，实测单次 80~130 秒，沿用 60 秒默认值会被前端提前掐断
const CHAT_TIMEOUT = 300000;

export const chatApi = {
  ask(params: AskParams, signal?: AbortSignal): Promise<ChatAnswer> {
    return http.post<ChatAnswer>('/api/chat/ask', params, { signal, timeout: CHAT_TIMEOUT });
  },
  clarify(params: ClarifyParams, signal?: AbortSignal): Promise<ChatAnswer> {
    return http.post<ChatAnswer>('/api/chat/clarify', params, { signal, timeout: CHAT_TIMEOUT });
  },
};
