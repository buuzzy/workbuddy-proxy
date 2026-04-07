/**
 * PM2 进程守护配置（Windows / macOS / Linux）
 *
 * 前置：已安装 Node.js，且 npm i -g pm2
 * 启动：在项目根目录执行  pm2 start ecosystem.config.cjs
 * 列表：pm2 ls
 * 日志：pm2 logs workbuddy-proxy
 * 停止：pm2 stop workbuddy-proxy
 * 删除：pm2 delete workbuddy-proxy
 *
 * 开机自启：pm2 save 后执行 pm2 startup，按终端提示完成（Windows 常需管理员权限）
 */
const isWin = process.platform === "win32";

const base = {
  name: "workbuddy-proxy",
  cwd: __dirname,
  instances: 1,
  exec_mode: "fork",
  autorestart: true,
  watch: false,
  max_restarts: 50,
  min_uptime: "5s",
  restart_delay: 3000,
  max_memory_restart: "512M",
  env: {
    PYTHONUNBUFFERED: "1",
  },
};

// Windows：PM2 对 pyenv 的 python.bat 作 interpreter 不稳定；用 cmd /c 与手动双击一致。
// 勿对 .cmd 使用 interpreter: "none"（易 spawn EINVAL）。
const winApp = {
  ...base,
  script: "cmd.exe",
  args: "/d /s /c run-proxy.cmd",
  interpreter: "none",
};

const unixApp = {
  ...base,
  script: "run-proxy.sh",
  interpreter: "bash",
};

module.exports = {
  apps: [isWin ? winApp : unixApp],
};
