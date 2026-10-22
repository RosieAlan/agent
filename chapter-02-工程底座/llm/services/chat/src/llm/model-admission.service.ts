import {
  HttpException,
  HttpStatus,
  Injectable,
} from '@nestjs/common';

const RATE_WINDOW_MS = 10_000; // 一个计数窗口为10秒
const MAX_REQUESTS_PER_WINDOW = 5; // 每个窗口最多接收5个任务
const MAX_CONCURRENT = 2; // 最多同时处理2个任务

@Injectable()
export class ModelAdmissionService {
  private activeRequests = 0; // 已接收且尚未结束的任务数
  private windowStartedAt = Date.now(); // 当前窗口开始时间
  private windowRequestCount = 0; // 当前窗口已接收的任务数

  enter(): () => void {
    // 返回类型“() => void”表示：这个方法会返回一个函数。
    const now = Date.now();

    if (now - this.windowStartedAt >= RATE_WINDOW_MS) {
      this.windowStartedAt = now;
      this.windowRequestCount = 0; // 窗口到期，重新累计接收次数
    }

    if (this.windowRequestCount >= MAX_REQUESTS_PER_WINDOW) {
      throw new HttpException(
        '请求过于频繁，请稍后再试',
        HttpStatus.TOO_MANY_REQUESTS,
      );
    }

    if (this.activeRequests >= MAX_CONCURRENT) {
      throw new HttpException(
        '当前分析任务较多，请稍后再试',
        HttpStatus.TOO_MANY_REQUESTS,
      );
    }

    this.windowRequestCount++;
    this.activeRequests++; // 检查通过，占用一个并发名额

    let released = false; // 记录本次任务是否已经归还名额

    return () => {
      if (released) return; // 重复调用时，保持只归还一次

      released = true;
      this.activeRequests--; // 归还本次任务占用的名额
    };
  }
}