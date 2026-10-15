'use client';

import {
  useEffect,
  useRef,
  useState,
} from 'react';
import type {
  AIUIResponse,
  UIAction,
} from '@/types/ui-types';
import {
  ComponentRenderer,
} from './ComponentRenderer';

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  'http://localhost:4001';

interface ChatMessage {
  id: string;
  role: 'user' | 'ai';
  content: string;
  response?: AIUIResponse;
}

export function AIChatContainer() {
  const sessionId = useRef('');
  const [messages, setMessages] =
    useState<ChatMessage[]>([
      {
        id: 'welcome',
        role: 'ai',
        content:
          '欢迎使用需求分析助手。请描述你的需求。',
      },
    ]);
  const [input, setInput] =
    useState('');
  const [loading, setLoading] =
    useState(false);
  const [error, setError] =
    useState('');

  useEffect(() => {
    sessionId.current =
      window.crypto.randomUUID();
  }, []);

  async function request(
    path: string,
    body: unknown,
  ): Promise<AIUIResponse> {
    const response = await fetch(
      `${API_BASE}/api/ui-chat/${path}`,
      {
        method: 'POST',
        headers: {
          'Content-Type':
            'application/json',
        },
        body: JSON.stringify(body),
      },
    );

    if (!response.ok) {
      throw new Error(
        `请求失败：HTTP ${response.status}`,
      );
    }

    return response.json() as Promise<AIUIResponse>;
  }

  function addAIMessage(
    response: AIUIResponse,
  ) {
    setMessages((current) => [
      ...current,
      {
        id: window.crypto.randomUUID(),
        role: 'ai',
        content: response.message,
        response,
      },
    ]);
  }

  async function handleSend() {
    const text = input.trim();

    if (
      !text ||
      loading ||
      !sessionId.current
    ) {
      return;
    }

    setInput('');
    setError('');
    setLoading(true);
    setMessages((current) => [
      ...current,
      {
        id: window.crypto.randomUUID(),
        role: 'user',
        content: text,
      },
    ]);

    try {
      const response = await request(
        'chat',
        {
          sessionId:
            sessionId.current,
          input: text,
        },
      );
      addAIMessage(response);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : '请求失败',
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleAction(
    action: UIAction,
  ) {
    if (
      loading ||
      !sessionId.current
    ) {
      return;
    }

    setError('');
    setLoading(true);
    setMessages((current) => [
      ...current,
      {
        id: window.crypto.randomUUID(),
        role: 'user',
        content:
          `操作：${action.componentType} → ${action.payload.type}`,
      },
    ]);

    try {
      const response = await request(
        'action',
        {
          sessionId:
            sessionId.current,
          action,
        },
      );
      addAIMessage(response);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : '操作失败',
      );
    } finally {
      setLoading(false);
    }
  }

  const latestAIMessageId =
    [...messages]
      .reverse()
      .find(
        (message) =>
          message.role === 'ai',
      )?.id;

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col p-6">
      <h1 className="mb-6 text-2xl font-bold">
        AI 需求分析助手
      </h1>

      <div className="flex-1 space-y-4">
        {messages.map((message) => (
          <article
            key={message.id}
            className={`max-w-[90%] rounded-xl p-4 ${
              message.role === 'user'
                ? 'ml-auto bg-blue-50'
                : 'border bg-white'
            }`}
          >
            <p className="whitespace-pre-wrap">
              {message.content}
            </p>

            {message.response
              ?.components.map(
                (component, index) => (
                  <div
                    key={index}
                    className={`mt-3 ${
                      message.id ===
                      latestAIMessageId
                        ? ''
                        : 'pointer-events-none opacity-60'
                    }`}
                  >
                    <ComponentRenderer
                      component={
                        component
                      }
                      initialData={
                        message.response
                          ?.context
                          ?.collectedData ??
                        undefined
                      }
                      onAction={
                        handleAction
                      }
                    />
                  </div>
                ),
              )}
          </article>
        ))}

        {loading && (
          <p className="text-sm text-gray-500">
            处理中…
          </p>
        )}
        {error && (
          <p className="text-sm text-red-600">
            {error}
          </p>
        )}
      </div>

      <div className="mt-6 flex gap-2">
        <input
          value={input}
          onChange={(event) =>
            setInput(event.target.value)
          }
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              void handleSend();
            }
          }}
          placeholder="输入你的需求"
          className="min-w-0 flex-1 rounded-lg border p-3"
        />
        <button
          type="button"
          disabled={loading}
          onClick={() =>
            void handleSend()
          }
          className="rounded-lg bg-blue-600 px-5 py-3 text-white disabled:opacity-50"
        >
          发送
        </button>
      </div>
    </main>
  );
}
