import { create } from 'zustand';
import type { ChatMessage, UserMessage, AssistantMessage } from '../types';
import { chatApi } from '../api/chat';
import { sessionApi } from '../api/session';
import { handleApiError } from '../api/client';

const SESSION_KEY = 'current_session_id';

// 会话切换序号：只认最后一次点击的结果
let sessionSeq = 0;

// 当前会话指针：刷新后还能接着问同一个会话，只有「新对话」或手动删除才清掉
function rememberSession(id: string | null) {
  if (id) localStorage.setItem(SESSION_KEY, id);
  else localStorage.removeItem(SESSION_KEY);
}

export function getStoredSessionId(): string | null {
  return localStorage.getItem(SESSION_KEY);
}

interface ChatState {
  sessionId: string | null;
  messages: ChatMessage[];
  loading: boolean;
  sessionLoading: boolean;
  error: string | null;
  abortController: AbortController | null;
  draft: string;

  ask: (question: string) => Promise<void>;
  submitClarify: (
    clarifyId: string,
    answer: { value?: string; text?: string },
  ) => Promise<void>;
  loadSession: (id: string) => Promise<void>;
  newSession: () => void;
  cancel: () => void;
  setError: (err: string | null) => void;
  setDraft: (text: string) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessionId: null,
  messages: [],
  loading: false,
  sessionLoading: false,
  error: null,
  abortController: null,
  draft: '',

  ask: async (question: string) => {
    const { sessionId } = get();
    const controller = new AbortController();
    set({ loading: true, error: null, abortController: controller });

    // 本地插入 user 气泡（临时 id）
    const tempUser: UserMessage = {
      message_id: `tmp_${Date.now()}`,
      session_id: sessionId || '',
      role: 'user',
      content: question,
      created_at: new Date().toISOString(),
    };
    set((s) => ({ messages: [...s.messages, tempUser] }));

    try {
      const resp = await chatApi.ask(
        { session_id: sessionId || undefined, question },
        controller.signal,
      );

      const assistant: AssistantMessage = {
        ...resp,
        role: 'assistant',
        content: resp.result?.narrative || '',
        created_at: new Date().toISOString(),
      };

      set((s) => ({
        sessionId: resp.session_id,
        messages: [...s.messages, assistant],
        loading: false,
        abortController: null,
      }));
      rememberSession(resp.session_id);
    } catch (e) {
      if ((e as Error).name === 'AbortError') {
        // 取消：移除 user 气泡
        set((s) => ({
          messages: s.messages.filter((m) => m.message_id !== tempUser.message_id),
          loading: false,
          abortController: null,
        }));
        return;
      }
      handleApiError(e);
      set({ loading: false, error: (e as Error).message, abortController: null });
    }
  },

  submitClarify: async (clarifyId, answer) => {
    const { sessionId } = get();
    if (!sessionId) return;
    const controller = new AbortController();
    set({ loading: true, abortController: controller });

    try {
      const resp = await chatApi.clarify(
        { session_id: sessionId, clarify_id: clarifyId, answer },
        controller.signal,
      );
      const assistant: AssistantMessage = {
        ...resp,
        role: 'assistant',
        content: resp.result?.narrative || '',
        created_at: new Date().toISOString(),
      };
      set((s) => ({ messages: [...s.messages, assistant], loading: false, abortController: null }));
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        handleApiError(e);
      }
      set({ loading: false, abortController: null });
    }
  },

  loadSession: async (id: string) => {
    // 切会话时丢弃过期响应，避免慢请求覆盖新会话
    const seq = ++sessionSeq;
    set({ sessionId: id, messages: [], sessionLoading: true, error: null });
    try {
      const resp = await sessionApi.getMessages(id);
      if (seq !== sessionSeq) return;
      set({ sessionId: id, messages: resp.items, loading: false, sessionLoading: false });
      rememberSession(id);
    } catch (e) {
      if (seq !== sessionSeq) return;
      handleApiError(e);
      rememberSession(null);
      set({ sessionId: null, messages: [], sessionLoading: false });
    }
  },

  newSession: () => {
    rememberSession(null);
    sessionSeq += 1;
    set({
      sessionId: null,
      messages: [],
      loading: false,
      sessionLoading: false,
      error: null,
      abortController: null,
    });
  },

  cancel: () => {
    const { abortController } = get();
    abortController?.abort();
  },

  setError: (err) => set({ error: err }),
  setDraft: (text) => set({ draft: text }),
}));
