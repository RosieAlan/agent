import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 660;

const COOKIE = 'course_access_token';
const USER_API = process.env.USER_API_URL || 'http://127.0.0.1:4002';
const CHAT_API = process.env.CHAT_API_URL || 'http://127.0.0.1:4001';
type Context = { params: Promise<{ path: string[] }> };

function clearSession(response: NextResponse) {
  response.cookies.set(COOKIE, '', { httpOnly: true, sameSite: 'lax', path: '/api/workbench', maxAge: 0 });
  return response;
}

async function handle(request: NextRequest, context: Context) {
  const { path } = await context.params;
  const route = path.join('/');
  const method = request.method;
  const origin = request.headers.get('origin');
  if (method !== 'GET' && origin && origin !== request.nextUrl.origin) {
    return NextResponse.json({ message: '请从当前页面提交请求' }, { status: 403 });
  }
  const token = request.cookies.get(COOKIE)?.value;

  try {
    if (route === 'login' && method === 'POST') {
      const body = await request.json();
      if (typeof body.username !== 'string' || typeof body.password !== 'string') {
        return NextResponse.json({ message: '请输入用户名和密码' }, { status: 400 });
      }
      const upstream = await fetch(`${USER_API}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: body.username, password: body.password }),
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(10_000)]),
        cache: 'no-store',
      });
      const payload = await upstream.json();
      if (!upstream.ok) return NextResponse.json(payload, { status: upstream.status });
      const data = payload.data ?? payload;
      if (!data.accessToken) throw new Error('登录响应缺少访问令牌');
      const response = NextResponse.json({ user: { username: data.user?.username ?? body.username } });
      response.cookies.set(COOKIE, data.accessToken, {
        httpOnly: true, sameSite: 'lax', secure: request.nextUrl.protocol === 'https:',
        path: '/api/workbench', maxAge: 3600,
      });
      return response;
    }
    if (route === 'session' && method === 'GET') {
      return NextResponse.json({ authenticated: Boolean(token) });
    }
    if (route === 'logout' && method === 'POST') {
      if (token) {
        await fetch(`${USER_API}/api/auth/logout`, {
          method: 'POST', headers: { Authorization: `Bearer ${token}` },
          signal: AbortSignal.timeout(5_000), cache: 'no-store',
        }).catch(() => {});
      }
      return clearSession(NextResponse.json({ ok: true }));
    }

    const conversations = route === 'conversations' && ['GET', 'POST'].includes(method);
    const conversation = /^conversations\/[a-zA-Z0-9_-]+$/.test(route) && method === 'DELETE';
    const history = /^conversations\/[a-zA-Z0-9_-]+\/messages$/.test(route) && method === 'GET';
    const stream = /^conversations\/[a-zA-Z0-9_-]+\/chat\/stream$/.test(route) && method === 'POST';
    if (!conversations && !conversation && !history && !stream) {
      return NextResponse.json({ message: '接口不存在' }, { status: 404 });
    }
    if (!token) return NextResponse.json({ message: '请先登录' }, { status: 401 });

    const upstream = await fetch(`${CHAT_API}/api/${route}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: method === 'POST' ? await request.text() : undefined,
      signal: stream ? request.signal : AbortSignal.any([request.signal, AbortSignal.timeout(15_000)]),
      cache: 'no-store',
    });
    if (upstream.status === 401) {
      return clearSession(NextResponse.json({ message: '登录已过期，请重新登录' }, { status: 401 }));
    }
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: {
        'Content-Type': upstream.headers.get('content-type') || 'application/json',
        'Cache-Control': 'no-store, no-transform',
        ...(stream ? { 'X-Accel-Buffering': 'no' } : {}),
      },
    });
  } catch (error) {
    if (error instanceof SyntaxError) return NextResponse.json({ message: '请求格式错误' }, { status: 400 });
    const service = route === 'login' || route === 'logout' ? '用户服务' : '聊天服务';
    return NextResponse.json({ message: `${service}连接失败，请确认服务已启动后重试。` }, { status: 503 });
  }
}

export const GET = handle;
export const POST = handle;
export const DELETE = handle;
