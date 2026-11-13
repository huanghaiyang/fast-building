#!/usr/bin/env node
/**
 * Fast Building 入口：用 npm 统一代理 Python 后端与 Vite 前端（替代原 PowerShell 脚本）。
 *
 *   npm start / npm run dev   后端 uvicorn --reload + 前端 Vite（HMR），前台运行，Ctrl+C 全部退出
 *   npm run prod              构建前端后由后端单端口 8756 托管（无热更新）
 *   npm run api               只启动后端（uvicorn --reload）
 *   npm run web               只启动前端（Vite）
 *   npm run build             只构建前端到 frontend/dist
 *
 * 说明：
 * - 可执行文件与端口来自项目根目录 .env（模板见 .env.example），真实环境变量优先；
 * - 前端 Vite dev server 的 host/port 由 .env 的 FB_FRONTEND_HOST / FB_FRONTEND_PORT 决定，
 *   /api、/out、/tex 反向代理到 FB_HOST:FB_PORT；
 * - 后端 --reload 监听 backend/ 与 generator/ 下的 .py（见 backend/run.py）；
 * - 两个子进程输出分别加 [api] / [web] 前缀，退出时整树结束，不会留下孤儿进程。
 */
import { spawn, execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const FRONTEND_DIR = path.join(ROOT, 'frontend');
const VITE_BIN = path.join(FRONTEND_DIR, 'node_modules', 'vite', 'bin', 'vite.js');
const BACKEND_ENTRY = path.join(ROOT, 'backend', 'run.py');

/** 读取项目根目录 .env（不覆盖真实环境变量）。 */
function loadDotenv(file) {
  if (!existsSync(file)) return;
  const content = readFileSync(file, 'utf8').replace(/^\uFEFF/, '');
  for (const raw of content.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) continue;
    const index = line.indexOf('=');
    const key = line.slice(0, index).trim();
    let value = line.slice(index + 1).trim();
    if (!key) continue;
    if (value.length >= 2 && value[0] === value[value.length - 1] && (value[0] === '"' || value[0] === "'")) {
      value = value.slice(1, -1);
    }
    if (process.env[key] === undefined) process.env[key] = value;
  }
}

loadDotenv(path.join(ROOT, '.env'));

const BACKEND_HOST = process.env.FB_HOST || '127.0.0.1';
const BACKEND_PORT = Number(process.env.FB_PORT || 8756);
const FRONTEND_HOST = process.env.FB_FRONTEND_HOST || '127.0.0.1';
const FRONTEND_PORT = Number(process.env.FB_FRONTEND_PORT || 5120);

const argv = process.argv.slice(2);
const wantsProd = argv.includes('--prod');
const wantsBuild = argv.includes('--build');
const onlyIndex = argv.indexOf('--only');
const only = onlyIndex >= 0 ? argv[onlyIndex + 1] : null;

if (argv.includes('--help') || argv.includes('-h')) {
  console.log('用法：node scripts/dev.mjs [--prod | --build | --only api|web]');
  process.exit(0);
}
if (only !== null && only !== 'api' && only !== 'web') {
  console.error(`--only 只接受 api 或 web，收到：${only}`);
  process.exit(1);
}

// ---------- 输出 ----------

const useColor = Boolean(process.stdout.isTTY);
const COLORS = { dev: '\u001b[90m', api: '\u001b[36m', web: '\u001b[35m' };
const RESET = '\u001b[0m';

const mark = (name) => (useColor ? `${COLORS[name] ?? ''}[${name}]${RESET} ` : `[${name}] `);
const say = (message) => process.stdout.write(`${mark('dev')}${message}\n`);

function forward(stream, name) {
  let pending = '';
  stream.setEncoding('utf8');
  stream.on('data', (chunk) => {
    pending += chunk;
    const lines = pending.split(/\r?\n/);
    pending = lines.pop() ?? '';
    for (const line of lines) process.stdout.write(`${mark(name)}${line}\n`);
  });
  stream.on('end', () => {
    if (pending) process.stdout.write(`${mark(name)}${pending}\n`);
  });
}

// ---------- 子进程生命周期 ----------

const children = new Set();
let exiting = false;

function killTree(child) {
  if (!child || child.exitCode !== null || !child.pid) return;
  try {
    if (process.platform === 'win32') {
      // uvicorn reload 看护进程与 vite/esbuild 都有子进程，必须整树结束
      spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true });
    } else {
      child.kill('SIGTERM');
    }
  } catch {
    // 进程可能已退出
  }
}

function shutdown(code, reason) {
  if (exiting) return;
  exiting = true;
  if (reason) say(reason);
  for (const child of children) killTree(child);
  setTimeout(() => process.exit(code), children.size > 0 ? 400 : 0);
}

process.on('SIGINT', () => shutdown(0, '收到 Ctrl+C，正在结束前后端 ...'));
process.on('SIGTERM', () => shutdown(0, '收到 SIGTERM，正在结束前后端 ...'));

function spawnChild(name, command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: options.cwd ?? ROOT,
    env: { ...process.env, ...(options.env ?? {}) },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });
  children.add(child);
  forward(child.stdout, name);
  forward(child.stderr, name);

  child.on('error', (error) => shutdown(1, `${name} 启动失败：${error.message}`));
  child.on('exit', (code, signal) => {
    children.delete(child);
    if (exiting) return;
    const detail = signal ? `signal=${signal}` : `code=${code}`;
    shutdown(code === 0 ? 0 : (code ?? 1), `${name} 已退出（${detail}），正在结束其余进程 ...`);
  });
  return child;
}

// ---------- 环境探测 ----------

function resolvePython() {
  const candidates = [
    process.env.FASTBUILD_PYTHON,
    path.join(ROOT, '.venv', 'Scripts', 'python.exe'),
    'D:\\thirdparty\\venvs\\fastbuild\\Scripts\\python.exe',
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

/** 返回占用指定端口的 PID 列表（Windows 用 netstat，其他平台返回空）。 */
function portOwners(port) {
  if (process.platform !== 'win32') return [];
  try {
    const output = execFileSync('netstat', ['-ano'], { encoding: 'utf8' });
    const pattern = new RegExp(`^\\s*TCP\\s+\\S+:${port}\\s+\\S+\\s+LISTENING\\s+(\\d+)\\s*$`);
    const pids = new Set();
    for (const line of output.split(/\r?\n/)) {
      const matched = line.match(pattern);
      if (matched) pids.add(matched[1]);
    }
    return [...pids];
  } catch {
    return [];
  }
}

function ensurePortFree(port, label) {
  const owners = portOwners(port);
  if (owners.length === 0) return true;
  say(`端口 ${port}（${label}）已被占用：PID ${owners.join(', ')}`);
  say('可能是上次未退出的进程，请先结束它再重试。');
  return false;
}

// ---------- 后端 / 前端 ----------

function startApi(reload) {
  const python = resolvePython();
  const args = [BACKEND_ENTRY];
  if (reload) args.push('--reload');
  say(
    reload
      ? `启动后端：${python}（uvicorn --reload，backend/ 与 generator/ 改动自动重启）`
      : `启动后端：${python}（无热更新）`,
  );
  return spawnChild('api', python, args, { cwd: path.join(ROOT, 'backend') });
}

function startWeb() {
  if (!existsSync(VITE_BIN)) {
    say('未找到 frontend/node_modules/vite，请先在 frontend 目录执行 npm install。');
    process.exit(1);
  }
  say(`启动前端：Vite dev server（HMR，${FRONTEND_HOST}:${FRONTEND_PORT}）`);
  return spawnChild('web', process.execPath, [VITE_BIN], { cwd: FRONTEND_DIR });
}

async function waitUntilReady(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline && !exiting) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(2000) });
      if (response.status < 500) return true;
    } catch {
      // 还没起来，继续等
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  return false;
}

// ---------- 构建 ----------

function runBuild() {
  if (!existsSync(VITE_BIN)) {
    say('未找到 frontend/node_modules/vite，请先在 frontend 目录执行 npm install。');
    process.exit(1);
  }
  // esbuild 的中间产物写在 TMP；系统临时目录不可写/不可删时构建会 "Access is denied"，
  // 这里把 TMP/TEMP 指到 node_modules 下（已被 git 忽略），保证构建稳定。
  const tmpDir = path.join(FRONTEND_DIR, 'node_modules', '.tmp');
  mkdirSync(tmpDir, { recursive: true });

  say('构建前端：vite build ...');
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [VITE_BIN, 'build'], {
      cwd: FRONTEND_DIR,
      env: { ...process.env, TMP: tmpDir, TEMP: tmpDir },
      stdio: 'inherit',
      windowsHide: true,
    });
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`vite build 失败（退出码 ${code}）`));
    });
  });
}

// ---------- 主流程 ----------

async function main() {
  if (wantsBuild) {
    await runBuild();
    say('构建完成：frontend/dist');
    return;
  }

  const needApi = !only || only === 'api';
  const needWeb = !only || only === 'web';

  if (needApi && !ensurePortFree(BACKEND_PORT, '后端')) process.exit(1);
  if (needWeb && !ensurePortFree(FRONTEND_PORT, '前端')) process.exit(1);

  if (wantsProd) {
    // 每次都重新构建，避免改了前端却仍托管旧的 dist
    await runBuild();
    startApi(false);
    if (!(await waitUntilReady(`http://${BACKEND_HOST}:${BACKEND_PORT}/api/health`, 30000))) {
      shutdown(1, '后端未能就绪');
      return;
    }
    say(`prod 已启动：http://${BACKEND_HOST}:${BACKEND_PORT}（单端口托管，无热更新）`);
    return;
  }

  if (needApi) startApi(true);
  if (needWeb) startWeb();

  const ready = [];
  if (needApi) {
    ready.push(
      waitUntilReady(`http://${BACKEND_HOST}:${BACKEND_PORT}/api/health`, 30000).then((ok) => ['后端', ok]),
    );
  }
  if (needWeb) {
    ready.push(
      waitUntilReady(`http://${FRONTEND_HOST}:${FRONTEND_PORT}/`, 60000).then((ok) => ['前端', ok]),
    );
  }

  for (const [name, ok] of await Promise.all(ready)) {
    if (!ok && !exiting) {
      shutdown(1, `${name}未能在超时时间内就绪`);
      return;
    }
  }
  if (exiting) return;

  say('dev 已启动：前后端热更新');
  if (needWeb) {
    say(`  前端  http://${FRONTEND_HOST}:${FRONTEND_PORT}   （HMR：改 frontend/src 即时生效）`);
    say(`  代理  /api、/out、/tex -> http://${BACKEND_HOST}:${BACKEND_PORT}`);
  }
  if (needApi) {
    say(`  后端  http://${BACKEND_HOST}:${BACKEND_PORT}   （--reload：改 backend/、generator/ 下 .py 自动重启）`);
    say(`  接口  http://${BACKEND_HOST}:${BACKEND_PORT}/api/health    ·    文档 http://${BACKEND_HOST}:${BACKEND_PORT}/docs`);
  }
  say('按 Ctrl+C 结束');
}

main().catch((error) => {
  say(`启动失败：${error.message}`);
  shutdown(1);
});
