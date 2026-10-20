'use client';

import { useRef, useState } from 'react';

export default function D03Page() {
  const [input, setInput] = useState('用户注册时必须绑定手机号，密码至少8位。');
  const [output, setOutput] = useState('等待提交');
  const [loading, setLoading] = useState(false);
  const requestRef = useRef<AbortController | null>(null);

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