'use client';

import { useRef, useState } from 'react';
async function readSse(response: Response, onText: (text: string) => void) {
  if (!response.body) throw new Error('响应缺少流式内容');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, '\n');
      let boundary: number;
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame.split('\n')
          .filter(line => line.startsWith('data:'))
          .map(line => line.slice(5).replace(/^ /, '')).join('\n');
        if (!data) continue;
        const event = JSON.parse(data);
        if (event === null || typeof event !== 'object') {
          throw new Error('事件格式错误');
        }
        if (event.type === 'delta') {
          if (typeof event.text !== 'string') throw new Error('文字事件格式错误');
          onText(event.text);
        } else if (event.type === 'error') {
          throw new Error(typeof event.message === 'string' ? event.message : '生成失败');
        } else if (event.type === 'done') {
          return;
        } else if (event.type !== 'start') {
          throw new Error('收到未知事件');
        }
      }
      if (done) throw new Error('连接已结束，结果尚未确认完成');
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
export default function D03Page() {
  const [input, setInput] = useState('用户注册时必须绑定手机号，密码至少8位。');
  const [output, setOutput] = useState('等待提交');
  const [loading, setLoading] = useState(false);
  const requestRef = useRef<AbortController | null>(null);
  async function sendStream() {
    if (requestRef.current) return;
    const controller = new AbortController();
    requestRef.current = controller;
    setLoading(true);
    setOutput('');
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/langchain/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
          body: JSON.stringify({ input }),
          signal: controller.signal,
        },
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}：${await response.text()}`);
      if (!response.headers.get('content-type')?.includes('text/event-stream')) {
        throw new Error('接口返回的内容类型与流式协议不符');
      }
      await readSse(response, text => setOutput(current => current + text));
      setOutput(current => current + '\n\n【生成完成】');
    } catch (error) {
      const message = controller.signal.aborted
        ? '已取消本次请求，以上内容尚未完成'
        : error instanceof Error ? error.message : '生成失败';
      setOutput(current => current + `\n\n【${message}】`);
    } finally {
      requestRef.current = null;
      setLoading(false);
    }
  }
  async function send(body: unknown) {
    if (requestRef.current) return;
    const controller = new AbortController();
    requestRef.current = controller;
    setLoading(true);
    setOutput('请求中……');

    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/langchain/structured`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: controller.signal,
        },
      );
      const data = await response.json();
      setOutput(`HTTP ${response.status}\n${JSON.stringify(data, null, 2)}`);
    } catch (error) {
      setOutput(
        controller.signal.aborted
          ? '已取消本次请求'
          : error instanceof Error ? error.message : '请求失败',
      );
    } finally {
      requestRef.current = null;
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 800, margin: '40px auto', padding: 24 }}>
      <h1>D04：结构化需求接口与请求取消</h1>
      <textarea
        aria-label="需求原文"
        rows={4}
        value={input}
        onChange={event => setInput(event.target.value)}
        style={{ width: '100%', border: '1px solid #888', padding: 12 }}
      />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, margin: '16px 0' }}>
        <button disabled={loading} onClick={() => send({ input })}>提交需求</button>
        <button disabled={loading} onClick={sendStream}>流式分析</button>
        <button disabled={loading} onClick={() => send({ input: 123 })}>验证数字输入</button>
        <button disabled={loading} onClick={() => send({ input: '' })}>验证空字符串</button>
        <button disabled={!loading} onClick={() => requestRef.current?.abort()}>
          取消本次请求
        </button>
      </div>
      <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{output}</pre>
    </main>
  );
}