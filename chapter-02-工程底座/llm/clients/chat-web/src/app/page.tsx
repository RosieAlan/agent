'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, readAnalysisStream, type ProgressEvent } from './workbench-client';
import styles from './workbench.module.css';

interface Conversation { id: string; title: string; createdAt: string }
interface Message {
  id: string;
  role: 'USER' | 'ASSISTANT';
  content: string;
  metadata?: { status?: string; activeExperts?: string[]; expertAnalyses?: Record<string, string> };
}
const expertLabels: Record<string, string> = {
  functional: '功能专家', performance: '性能专家', security: '安全专家', compliance: '合规专家',
};
const example = '企业管理员批量导入 Excel，目的是减少录入时间，优先级 P1。每次最多一万行，仅支持 xlsx。超限文件被拒绝，导入后展示成功数和失败数，错误行和原因可导出。仅有导入权限的人可操作，错误文件仅提交人可下载，支持多人同时导入。';

function Report({ content }: { content: string }) {
  return <div className={styles.report}>{content.split('\n').map((line, index) => {
    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (heading) return <h3 key={index}>{heading[2]}</h3>;
    return <p key={index}>{line || '\u00a0'}</p>;
  })}</div>;
}

export default function Home() {
  const [ready, setReady] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [loggingIn, setLoggingIn] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState<ProgressEvent[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const operation = useRef(false);
  const abort = useRef<AbortController | null>(null);
  const historyVersion = useRef(0);
  const bottom = useRef<HTMLDivElement>(null);

  async function refreshConversations() {
    const items = await api<Conversation[]>('conversations');
    setConversations(items);
    return items;
  }

  async function openConversation(id: string) {
    if (operation.current) return;
    const version = ++historyVersion.current;
    setActiveId(id);
    setMessages([]);
    setProgress([]);
    setError('');
    setLoadingHistory(true);
    try {
      const history = await api<Message[]>(`conversations/${id}/messages`);
      if (version === historyVersion.current) setMessages(history);
    } catch (err) {
      if (version === historyVersion.current) setError((err as Error).message);
    } finally {
      if (version === historyVersion.current) setLoadingHistory(false);
    }
  }

  useEffect(() => {
    const unauthorized = () => {
      abort.current?.abort();
      ++historyVersion.current;
      setLoggedIn(false);
      setMessages([]);
      setConversations([]);
      setActiveId(null);
      setError('登录已过期，请重新登录');
    };
    window.addEventListener('workbench:unauthorized', unauthorized);
    let mounted = true;
    void (async () => {
      try {
        const session = await api<{ authenticated: boolean }>('session');
        if (!mounted) return;
        setLoggedIn(session.authenticated);
        if (session.authenticated) {
          const items = await refreshConversations();
          if (mounted && items[0]) await openConversation(items[0].id);
        }
      } catch (err) {
        if (mounted) setError((err as Error).message);
      } finally {
        if (mounted) setReady(true);
      }
    })();
    return () => {
      mounted = false;
      abort.current?.abort();
      window.removeEventListener('workbench:unauthorized', unauthorized);
    };
  }, []);

  useEffect(() => {
    if (!busy) return;
    const start = Date.now();
    setElapsed(0);
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [busy]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, progress]);

  async function login(event: FormEvent) {
    event.preventDefault();
    if (loggingIn) return;
    setLoggingIn(true);
    setError('');
    try {
      await api('login', { method: 'POST', body: JSON.stringify({ username, password }) });
      setPassword('');
      const items = await refreshConversations();
      if (items[0]) await openConversation(items[0].id);
      setLoggedIn(true);
    } catch (err) { setError((err as Error).message); }
    finally { setLoggingIn(false); }
  }

  async function logout() {
    abort.current?.abort();
    try { await api('logout', { method: 'POST' }); }
    catch (err) { setError((err as Error).message); return; }
    ++historyVersion.current;
    setLoggedIn(false);
    setConversations([]);
    setMessages([]);
    setActiveId(null);
    setProgress([]);
    setError('');
  }

  function newConversation() {
    if (operation.current) return;
    ++historyVersion.current;
    setActiveId(null);
    setMessages([]);
    setProgress([]);
    setInput('');
    setError('');
    setLoadingHistory(false);
  }

  async function removeConversation() {
    if (!activeId || operation.current || !window.confirm('删除此会话及其全部消息？')) return;
    try {
      await api(`conversations/${activeId}`, { method: 'DELETE' });
      newConversation();
      await refreshConversations();
    } catch (err) { setError((err as Error).message); }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    const text = input.trim();
    if (!text || operation.current || loadingHistory) return;
    operation.current = true;
    setBusy(true);
    setError('');
    setProgress([]);
    const controller = new AbortController();
    abort.current = controller;
    let id = activeId;
    try {
      if (!id) {
        const conversation = await api<Conversation>('conversations', {
          method: 'POST', body: JSON.stringify({ title: text.slice(0, 28) }), signal: controller.signal,
        });
        id = conversation.id;
        setActiveId(id);
        setConversations((items) => [conversation, ...items]);
      }
      setMessages((items) => [...items, { id: crypto.randomUUID(), role: 'USER', content: text }]);
      setInput('');
      const response = await fetch(`/api/workbench/conversations/${id}/chat/stream`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: text }), signal: controller.signal,
      });
      const result = await readAnalysisStream(response, (update) => {
        setProgress((items) => [...items.filter((item) => item.step !== update.step), update]);
      });
      if (result.status === 'failed') throw new Error(result.error || result.report || '分析失败，请稍后重试');
      const content = result.status === 'need_clarification'
        ? '请补充以下信息：\n' + (result.clarificationQuestions ?? []).map((question, i) => `${i + 1}. ${question}`).join('\n')
        : result.report || '分析已完成';
      setMessages((items) => [...items, {
        id: crypto.randomUUID(), role: 'ASSISTANT', content,
        metadata: { status: result.status, activeExperts: result.activeExperts, expertAnalyses: result.expertAnalyses },
      }]);
      setProgress([]);
    } catch (err) {
      setError(controller.signal.aborted
        ? '已停止等待。已完成的历史记录可以通过刷新会话查看。'
        : (err as Error).message);
    } finally {
      operation.current = false;
      setBusy(false);
      abort.current = null;
    }
  }

  if (!ready) return <main className={styles.loading}>正在加载工作区…</main>;

  if (!loggedIn) return <main className={styles.loginPage}>
    <section className={styles.loginIntro}>
      <span className={styles.brand}>Autix · 需求分析</span>
      <h1>从一个想法，<br />到一份清晰的需求。</h1>
      <p>描述业务目标，补充关键约束，让不同领域的专家共同检查需求并生成报告。</p>
      <div className={styles.loginFlow}>描述需求 <span>→</span> 专家分析 <span>→</span> 查看报告</div>
    </section>
    <form className={styles.loginForm} onSubmit={login}>
      <h2>登录工作区</h2><p>使用课程用户系统中的账号。</p>
      <label>用户名<input name="username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required /></label>
      <label>密码<input name="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
      {error && <div className={styles.error} role="alert">{error}</div>}
      <button className={styles.primary} type="submit" disabled={loggingIn}>{loggingIn ? '正在登录…' : '登录'}</button>
    </form>
  </main>;

  const activeTitle = conversations.find((conversation) => conversation.id === activeId)?.title || '新需求';
  return <div className={styles.workspace}>
    <aside className={styles.sidebar}>
      <a className={styles.brand} href="/">Autix<span>需求分析工作区</span></a>
      <button className={styles.primary} onClick={newConversation} disabled={busy}>＋ 新建会话</button>
      <p className={styles.sidebarLabel}>我的会话</p>
      <nav aria-label="会话列表" className={styles.conversations}>
        {conversations.map((conversation) => <button key={conversation.id} disabled={busy}
          className={activeId === conversation.id ? styles.selectedConversation : styles.conversation}
          onClick={() => void openConversation(conversation.id)}>{conversation.title}</button>)}
        {!conversations.length && <p className={styles.hint}>发送一条需求后，会自动保存为会话。</p>}
      </nav>
      <div className={styles.sidebarFooter}><a href="/ui-demo">交互组件练习</a><button onClick={() => void logout()} disabled={busy}>退出登录</button></div>
    </aside>
    <main className={styles.main}>
      <header className={styles.header}><div><span className={styles.hint}>需求分析</span><h1>{activeTitle}</h1></div>
        <div className={styles.headerActions}>
          {activeId && <button disabled={busy || loadingHistory} onClick={() => void openConversation(activeId)}>刷新历史</button>}
          {activeId && <button disabled={busy || loadingHistory} onClick={() => void removeConversation()}>删除会话</button>}
        </div>
      </header>
      <section className={styles.thread} aria-label="对话记录">
        {loadingHistory && <p className={styles.hint}>正在读取历史消息…</p>}
        {!messages.length && !loadingHistory && <div className={styles.empty}>
          <span className={styles.emptyMark}>需</span><h2>这次想分析什么需求？</h2>
          <p>写出谁来使用、要完成什么，以及数据量、权限、验收标准等约束。信息不足时，助手会继续追问。</p>
          <button className={styles.example} onClick={() => setInput(example)}>试试：批量导入 Excel 的完整需求</button>
        </div>}
        {messages.map((message) => <article key={message.id} className={message.role === 'USER' ? styles.userMessage : styles.assistantMessage}>
          <div className={styles.messageLabel}>{message.role === 'USER' ? '你' : '需求分析助手'}</div>
          <Report content={message.content} />
          {message.metadata?.activeExperts?.length ? <div className={styles.expertTags}>{message.metadata.activeExperts.map((name) => <span key={name}>{expertLabels[name] || name}</span>)}</div> : null}
          {message.metadata?.expertAnalyses && Object.entries(message.metadata.expertAnalyses).map(([name, content]) =>
            <details className={styles.expertDetail} key={name}><summary>{expertLabels[name] || name}的分析</summary><Report content={content} /></details>)}
        </article>)}
        {busy && <section className={styles.progress} aria-live="polite">
          <div className={styles.progressTitle}><strong>正在分析需求</strong><span>已用时 {elapsed} 秒</span></div>
          <ul>{progress.length ? progress.map((item) => <li key={item.step}>
            <span className={item.status === 'running' ? styles.running : item.status === 'failed' ? styles.failed : styles.done} />
            {item.label}<span>{item.status === 'running' ? '进行中' : item.status === 'failed' ? '失败' : '完成'}</span>
          </li>) : <li>正在建立连接…</li>}</ul>
          <p>报告完成后会自动显示；分析期间请保持页面打开。</p>
          <button onClick={() => abort.current?.abort()}>停止分析</button>
        </section>}
        <div ref={bottom} />
      </section>
      <div className={styles.composerArea}>
        {error && <div role="alert" className={styles.error}>{error}</div>}
        <form className={styles.composer} onSubmit={send}>
          <label className={styles.inputLabel} htmlFor="requirement">需求内容</label>
          <textarea id="requirement" value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }}
            placeholder="描述需求或补充上一次的追问…" rows={3} disabled={busy || loadingHistory} />
          <div className={styles.composerFooter}><span>Ctrl + Enter 发送 · 历史记录自动保存</span>
            <button className={styles.primary} type="submit" disabled={busy || loadingHistory || !input.trim()}>{busy ? '分析中…' : '发送需求'}</button></div>
        </form>
      </div>
    </main>
  </div>;
}
