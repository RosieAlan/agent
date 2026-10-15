import 'reflect-metadata';
import '../src/load-env.js';
import { JwtService } from '@nestjs/jwt';

const jwt = new JwtService({
  secret: process.env.JWT_SECRET,
  signOptions: { expiresIn: '24h' },
});

const userId = process.argv[2] ?? 'u-1001';

const token = jwt.sign({
  sub: userId,
  username: userId,
  sessionId: 'local-session',
});

console.log(`userId = ${userId}`);
console.log(token);
