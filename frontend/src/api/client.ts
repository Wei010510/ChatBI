// fetch 封装：统一 ApiResponse 解包、超时、AbortController、错误码映射。
import { message } from 'antd';
import type { ApiResponse, ErrorCode } from '../types';

const DEFAULT_TIMEOUT = 60000;

export class ApiError extends Error {
  code: ErrorCode | string;
  httpStatus: number;

  constructor(message: string, code: ErrorCode | string, httpStatus: number) {
    super(message);
    this.code = code;
    this.httpStatus = httpStatus;
  }
}

// 鉴权预留：本版空实现
export function attachAuthHeader(headers: Headers): Headers {
  return headers;
}

export interface RequestOptions {
  signal?: AbortSignal;
  timeout?: number;
}

async function request<T>(
  url: string,
  options: RequestInit & RequestOptions = {},
): Promise<T> {
  const { signal, timeout = DEFAULT_TIMEOUT, ...rest } = options;

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeout);

  if (signal) {
    signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  const headers = new Headers(rest.headers);
  headers.set('Content-Type', 'application/json');
  attachAuthHeader(headers);

  try {
    const resp = await fetch(url, {
      ...rest,
      headers,
      signal: controller.signal,
    });

    const body: ApiResponse<T> = await resp.json().catch(() => ({
      code: 'INTERNAL',
      message: resp.statusText,
      data: null as T,
      trace_id: '',
    }));

    if (resp.ok && body.code === '0') {
      return body.data;
    }

    throw new ApiError(body.message, body.code || 'INTERNAL', resp.status);
  } catch (e) {
    if (e instanceof ApiError) {
      throw e;
    }
    if ((e as Error).name === 'AbortError') {
      // 超时触发的中断要显式报错，不能和用户主动取消混为一谈
      if (timedOut) {
        throw new ApiError('请求超时，请稍后重试', 'TIMEOUT', 0);
      }
      throw e;
    }
    throw new ApiError((e as Error).message || '网络异常', 'INTERNAL', 0);
  } finally {
    clearTimeout(timer);
  }
}

export const http = {
  get<T>(url: string, opts?: RequestOptions): Promise<T> {
    return request<T>(url, { method: 'GET', ...opts });
  },
  post<T>(url: string, body?: unknown, opts?: RequestOptions): Promise<T> {
    return request<T>(url, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
      ...opts,
    });
  },
  patch<T>(url: string, body?: unknown, opts?: RequestOptions): Promise<T> {
    return request<T>(url, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
      ...opts,
    });
  },
  delete<T>(url: string, opts?: RequestOptions): Promise<T> {
    return request<T>(url, { method: 'DELETE', ...opts });
  },
};

// 错误码 → 前端展示
export function handleApiError(e: unknown) {
  if (e instanceof ApiError) {
    if (e.httpStatus === 404 && e.code === 'SESSION_NOT_FOUND') {
      message.error('会话不存在，已开启新对话');
      return;
    }
    if (e.httpStatus === 422) {
      message.error('这次结果不能存为报表');
      return;
    }
    if (e.httpStatus === 500) {
      message.error('服务器异常，请重试');
      return;
    }
    message.error(e.message || '请求失败');
  } else if ((e as Error).name !== 'AbortError') {
    message.error('网络异常');
  }
}
