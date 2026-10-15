import { Injectable } from '@nestjs/common';
import { APP_NAME } from '@autix/contracts';

@Injectable()
export class AppService {
  getHello() {
    return {
      message: `Hello from Chat, APP_NAME=${APP_NAME}`,
    };
  }

  getHealth() {
    return { ok: true };
  }
}
