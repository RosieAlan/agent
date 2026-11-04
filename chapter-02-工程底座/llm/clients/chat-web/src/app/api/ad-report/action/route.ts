export const runtime = 'nodejs'; // 在Next.js服务端运行。

export async function POST(request: Request) {
  const origin = request.headers.get('origin');

  if (origin && origin !== new URL(request.url).origin) {
    // 检查浏览器请求是否来自当前网站。
    return Response.json(
      { message: '请从当前页面提交' },
      { status: 403 },
    );
  }

  let body;

  try {
    body = await request.json(); // 读取浏览器提交的JSON。
  } catch {
    return Response.json(
      { message: '请求需要JSON格式' },
      { status: 400 },
    );
  }

  // Record<string, string>表示“字符串键 → 字符串值”的对象。
  const tasks: Record<string, string> = {
    generate_report:
      '生成简洁广告分析报告，包含指标、数据局限、待确认信息与建议。',
    explain_metrics:
      '解释花费、归因销售额和ROAS，结合本次报表说明计算过程。',
  };

  if (
    !body || typeof body !== 'object' ||
    typeof body.campaignId !== 'string' ||
    !/^AD-[A-Za-z0-9-]{1,60}$/.test(body.campaignId) ||
    typeof body.actionId !== 'string' ||
    !Object.hasOwn(tasks, body.actionId)
  ) {
    // hasOwn检查tasks自己定义的操作，例如generate_report。
    return Response.json(
      { message: '广告编号或操作编号无效' },
      { status: 422 },
    );
  }

  const timeout = AbortSignal.timeout(125_000); // 最多等待125秒。

  try {
    const baseUrl =
      process.env.PYTHON_API_BASE_URL || 'http://127.0.0.1:8000';

    const response = await fetch(`${baseUrl}/ads/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        // 拼出明确任务，复用Python已有的input参数。
        input:
          `广告活动${body.campaignId}。${tasks[body.actionId]}` +
          '先用工具查数据，标明来源。' +
          '盈利判断说明所需毛利及其他费用；本次只查询和分析。',
      }),
      cache: 'no-store',
      // 当前请求断开或等待超时，都会取消这次转发等待。
      signal: AbortSignal.any([request.signal, timeout]),
    });

    if (!response.ok) {
      return Response.json(
        {
          message: response.status === 504
            ? '模型响应超时，请稍后重新点击；本次分析尚未完成'
            : '分析暂时失败，请查看Python日志后重试',
        },
        { status: response.status >= 500 ? response.status : 502 },
      );
    }

    const result = await response.json(); // Python返回的结果。

    if (
      !result ||
      typeof result.answer !== 'string' ||
      !result.answer.trim() ||
      !['completed', 'limit_reached'].includes(result.status)
    ) {
      return Response.json(
        { message: '分析结果格式异常或内容为空' },
        { status: 502 },
      );
    }

    // 页面当前只需要状态与回答。
    return Response.json({
      status: result.status,
      answer: result.answer,
    });
  } catch (error) {
    console.error('[ad-action] request failed', error);

    return Response.json(
      {
        message: timeout.aborted
          ? '分析等待超时，请稍后重试'
          : '分析服务连接失败',
      },
      { status: timeout.aborted ? 504 : 503 },
    );
  }
}
