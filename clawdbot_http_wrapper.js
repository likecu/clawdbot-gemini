#!/usr/bin/env node

/**
 * Clawdbot HTTP Wrapper (WebSocket 版本)
 * 通过 WebSocket 持久连接与 OpenClaw Gateway 通信，消除 CLI 启动延迟。
 * 
 * 协议流程：
 * 1. 连接 ws://127.0.0.1:18789
 * 2. 收到 connect.challenge 事件（含 nonce）
 * 3. 发送 connect 请求（含 auth token、client info）
 * 4. 收到 connect 响应表示握手成功
 * 5. 发送 agent 方法调用处理聊天消息
 */

const express = require('express');
const http = require('http');
const { randomUUID } = require('crypto');
const bodyParser = require('body-parser');
const path = require('path');
const os = require('os');
const fs = require('fs');

// ========== 配置 ==========

const CALLBACK_URL = process.env.CALLBACK_URL || 'http://127.0.0.1:8081/api/clawdbot/callback';
const GATEWAY_URL = process.env.GATEWAY_URL || 'ws://127.0.0.1:18789';
const PROTOCOL_VERSION = 3;

/**
 * 从 clawdbot.json 中读取 Gateway 认证令牌
 * @returns {string|undefined} Gateway 认证令牌
 */
function loadGatewayToken() {
    const configPath = path.join(os.homedir(), '.clawdbot/clawdbot.json');
    try {
        const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
        return config.gateway?.auth?.token;
    } catch (e) {
        console.error(`[CONFIG] 无法读取 clawdbot.json: ${e.message}`);
        return undefined;
    }
}

const GATEWAY_TOKEN = process.env.GATEWAY_TOKEN || loadGatewayToken();

// ========== WebSocket 持久连接客户端 ==========

/**
 * OpenClaw Gateway WebSocket 客户端
 * 维护与 Gateway 的持久连接，支持自动重连和请求管理。
 */
class GatewayWsClient {
    constructor() {
        /** @type {import('ws')|null} WebSocket 实例 */
        this.ws = null;
        /** @type {Map<string, {resolve: Function, reject: Function, expectFinal: boolean}>} 等待响应的请求 */
        this.pending = new Map();
        /** @type {boolean} 是否已完成握手 */
        this.connected = false;
        /** @type {boolean} 是否已关闭 */
        this.closed = false;
        /** @type {string|null} 握手 nonce */
        this.connectNonce = null;
        /** @type {boolean} 是否已发送 connect */
        this.connectSent = false;
        /** @type {number} 重连退避时间（毫秒） */
        this.backoffMs = 1000;
        /** @type {Function|null} 握手成功后的回调 */
        this._onReady = null;
        /** @type {Promise<void>|null} 连接就绪 Promise */
        this._readyPromise = null;
        /** @type {number|null} tick 定时器 */
        this.tickTimer = null;
        /** @type {number|null} 最后一次 tick 时间 */
        this.lastTick = null;
        /** @type {number} tick 检查间隔 */
        this.tickIntervalMs = 30000;
    }

    /**
     * 启动连接
     * @returns {Promise<void>} 连接就绪后 resolve
     */
    start() {
        if (this._readyPromise) return this._readyPromise;
        this._readyPromise = new Promise((resolve) => {
            this._onReady = resolve;
        });
        this._connect();
        return this._readyPromise;
    }

    /**
     * 建立 WebSocket 连接
     * @private
     */
    _connect() {
        if (this.closed) return;

        // 使用 ws 库（Node.js 原生 WebSocket 在 Node 22 中仍是实验性的）
        const WebSocket = require('ws');

        console.log(`[WS] 正在连接 ${GATEWAY_URL}...`);
        this.connectSent = false;
        this.connectNonce = null;
        this.connected = false;

        this.ws = new WebSocket(GATEWAY_URL, {
            maxPayload: 25 * 1024 * 1024,
        });

        this.ws.on('open', () => {
            console.log(`[WS] WebSocket 已打开，等待 connect.challenge...`);
            // 设置超时：如果 750ms 内没收到 challenge，直接发送 connect
            this._connectTimer = setTimeout(() => {
                this._sendConnect();
            }, 750);
        });

        this.ws.on('message', (data) => {
            this._handleMessage(data.toString());
        });

        this.ws.on('close', (code, reason) => {
            const reasonText = reason?.toString() || '';
            console.log(`[WS] 连接关闭: code=${code}, reason=${reasonText}`);
            this.ws = null;
            this.connected = false;
            this._flushPendingErrors(new Error(`gateway closed (${code}): ${reasonText}`));
            this._scheduleReconnect();
        });

        this.ws.on('error', (err) => {
            console.error(`[WS] 连接错误: ${err.message}`);
        });
    }

    /**
     * 发送 connect 握手请求
     * @private
     */
    _sendConnect() {
        if (this.connectSent) return;
        this.connectSent = true;

        if (this._connectTimer) {
            clearTimeout(this._connectTimer);
            this._connectTimer = null;
        }

        const auth = GATEWAY_TOKEN ? { token: GATEWAY_TOKEN } : undefined;
        const instanceId = randomUUID();

        const params = {
            minProtocol: PROTOCOL_VERSION,
            maxProtocol: PROTOCOL_VERSION,
            client: {
                id: 'cli',
                displayName: 'QQ HTTP Wrapper',
                version: '2.0.0',
                platform: process.platform,
                mode: 'cli',
                instanceId,
            },
            caps: [],
            auth,
            role: 'operator',
            scopes: ['operator.admin'],
        };

        if (this.connectNonce) {
            // 将 nonce 包含在设备鉴权中（如果有的话），这里简化处理
        }

        this._sendRequest('connect', params)
            .then((helloOk) => {
                console.log(`[WS] ✅ Gateway 握手成功!`);
                this.connected = true;
                this.backoffMs = 1000;

                // 设置 tick 监控
                this.tickIntervalMs = helloOk?.policy?.tickIntervalMs || 30000;
                this.lastTick = Date.now();
                this._startTickWatch();

                // 通知就绪
                if (this._onReady) {
                    this._onReady();
                    this._onReady = null;
                }
            })
            .catch((err) => {
                console.error(`[WS] ❌ Gateway 握手失败: ${err.message}`);
                this.ws?.close(1008, 'connect failed');
            });
    }

    /**
     * 处理收到的 WebSocket 消息
     * @private
     * @param {string} raw - 原始 JSON 字符串
     */
    _handleMessage(raw) {
        try {
            const parsed = JSON.parse(raw);

            // 事件帧：包含 event 字段
            if (parsed.event) {
                if (parsed.event === 'connect.challenge') {
                    const nonce = parsed.payload?.nonce;
                    if (nonce) {
                        this.connectNonce = nonce;
                        this._sendConnect();
                    }
                    return;
                }
                if (parsed.event === 'tick') {
                    this.lastTick = Date.now();
                }
                return;
            }

            // 响应帧：包含 id 和 ok 字段
            if ('id' in parsed && 'ok' in parsed) {
                const pending = this.pending.get(parsed.id);
                if (!pending) return;

                // 如果是 expectFinal 且当前只是 accepted 确认，继续等待
                const status = parsed.payload?.status;
                if (pending.expectFinal && status === 'accepted') {
                    console.log(`[WS] 请求 ${parsed.id.substring(0, 8)} 已接受，等待最终结果...`);
                    return;
                }

                this.pending.delete(parsed.id);
                if (parsed.ok) {
                    pending.resolve(parsed.payload);
                } else {
                    pending.reject(new Error(parsed.error?.message || 'unknown error'));
                }
            }
        } catch (err) {
            console.error(`[WS] 消息解析错误: ${err.message}`);
        }
    }

    /**
     * 发送 RPC 请求到 Gateway
     * @param {string} method - RPC 方法名
     * @param {Object} params - 方法参数
     * @param {Object} [opts] - 选项
     * @param {boolean} [opts.expectFinal=false] - 是否等待最终响应（而非 accepted 确认）
     * @returns {Promise<Object>} 响应 payload
     * @throws {Error} 连接未建立或请求超时
     */
    request(method, params, opts = {}) {
        return this._sendRequest(method, params, opts);
    }

    /**
     * 内部发送请求方法
     * @private
     */
    _sendRequest(method, params, opts = {}) {
        if (!this.ws || this.ws.readyState !== 1) { // WebSocket.OPEN = 1
            return Promise.reject(new Error('gateway not connected'));
        }

        const id = randomUUID();
        const frame = { type: 'req', id, method, params };
        const expectFinal = opts.expectFinal === true;

        const promise = new Promise((resolve, reject) => {
            this.pending.set(id, { resolve, reject, expectFinal });
        });

        this.ws.send(JSON.stringify(frame));
        return promise;
    }

    /**
     * 清除所有等待中的请求并以错误方式拒绝
     * @private
     */
    _flushPendingErrors(err) {
        for (const [, p] of this.pending) {
            p.reject(err);
        }
        this.pending.clear();
    }

    /**
     * 安排重连
     * @private
     */
    _scheduleReconnect() {
        if (this.closed) return;
        if (this.tickTimer) {
            clearInterval(this.tickTimer);
            this.tickTimer = null;
        }
        const delay = this.backoffMs;
        this.backoffMs = Math.min(this.backoffMs * 2, 30000);
        console.log(`[WS] ${delay}ms 后重连...`);

        // 重置 ready promise
        this._readyPromise = new Promise((resolve) => {
            this._onReady = resolve;
        });

        setTimeout(() => this._connect(), delay);
    }

    /**
     * 启动 tick 超时监控
     * @private
     */
    _startTickWatch() {
        if (this.tickTimer) clearInterval(this.tickTimer);
        const interval = Math.max(this.tickIntervalMs, 1000);
        this.tickTimer = setInterval(() => {
            if (this.closed) return;
            if (!this.lastTick) return;
            const gap = Date.now() - this.lastTick;
            if (gap > this.tickIntervalMs * 2) {
                console.warn(`[WS] Tick 超时，关闭连接...`);
                this.ws?.close(4000, 'tick timeout');
            }
        }, interval);
    }

    /**
     * 检查连接是否就绪
     * @returns {boolean}
     */
    isReady() {
        return this.connected && this.ws && this.ws.readyState === 1;
    }

    /**
     * 确保连接就绪，按需等待
     * @returns {Promise<void>}
     */
    async ensureReady() {
        if (this.isReady()) return;
        if (this._readyPromise) return this._readyPromise;
        return this.start();
    }

    /**
     * 停止客户端
     */
    stop() {
        this.closed = true;
        if (this.tickTimer) {
            clearInterval(this.tickTimer);
            this.tickTimer = null;
        }
        this.ws?.close();
        this.ws = null;
        this._flushPendingErrors(new Error('gateway client stopped'));
    }
}

// ========== Express 服务 ==========

const app = express();
const port = 3009;

app.use(bodyParser.json());

// 全局 Gateway 客户端实例
const gatewayClient = new GatewayWsClient();

// 健康检查接口
app.get('/health', (req, res) => {
    res.json({
        status: 'ok',
        service: 'clawdbot-http-wrapper',
        mode: 'websocket',
        gatewayConnected: gatewayClient.isReady(),
    });
});

/**
 * 处理聊天请求的 POST 接口
 * 通过 WebSocket 持久连接发送消息到 Gateway，消除 CLI 启动延迟。
 * @param {Object} req.body.message - 用户输入的消息内容
 * @param {Object} req.body.session_id - 会话唯一标识符
 */
app.post('/chat', async (req, res) => {
    const { message, session_id, callback_session_id } = req.body;

    if (!message) {
        return res.status(400).json({ error: 'Message is required' });
    }

    const startTime = Date.now();
    const sessionId = session_id || 'qq:user:unknown';
    // callback_session_id 用于消息回调路由，包含消息类型和目标 chat_id
    const callbackSessionId = callback_session_id || sessionId;

    console.log(`[${new Date().toISOString()}] /chat SessionID=${sessionId}, CallbackID=${callbackSessionId}`);
    console.log(`[${new Date().toISOString()}] Message=${message?.substring(0, 30)}...`);

    const enrichedMessage = `${message}\n\n(Note: You have FULL access to tools. If you need to search the web, you MUST strictly output the text \`[Search: your_keyword]\` and NOTHING else, do NOT try to use the 'web_search' tool. Please use the 'exec' tool to run Python scripts or other commands to get actual results. Do NOT simulate execution.)`;

    try {
        // 确保 Gateway 连接就绪
        await gatewayClient.ensureReady();

        const idempotencyKey = randomUUID();
        const connectLatency = Date.now() - startTime;
        console.log(`[${new Date().toISOString()}] Gateway 就绪耗时: ${connectLatency}ms`);

        // 通过 WebSocket 发送 agent 请求
        // sessionKey 使用 session_id（用户维度），确保不同用户有独立的 AI 记忆
        const result = await gatewayClient.request('agent', {
            message: enrichedMessage,
            sessionKey: `agent:main:${sessionId}`,
            thinking: 'high',
            deliver: false,
            channel: 'webchat',
            timeout: 180,
            idempotencyKey,
        }, { expectFinal: true });

        const totalLatency = Date.now() - startTime;
        console.log(`[${new Date().toISOString()}] Agent 响应完成，总耗时: ${totalLatency}ms`);

        // 提取回复内容
        let sentCount = 0;
        let finalReply = '任务已完成。';
        const payloads = result?.payloads || result?.result?.payloads || [];

        for (const p of payloads) {
            if (p.text) {
                // 使用 callbackSessionId 进行回调路由（包含消息类型和目标 chat_id）
                console.log(`[${new Date().toISOString()}] Routing callback to: ${callbackSessionId}`);
                sendCallback(callbackSessionId, p.text);
                sentCount++;
                finalReply = p.text;
            }
        }

        res.json({
            reply: finalReply,
            segments_sent: sentCount,
            is_callback_mode: sentCount > 0,
            latency_ms: totalLatency,
            mode: 'websocket',
        });

    } catch (err) {
        const totalLatency = Date.now() - startTime;
        console.error(`[${new Date().toISOString()}] 请求失败 (${totalLatency}ms): ${err.message}`);
        res.status(500).json({
            error: err.message,
            latency_ms: totalLatency,
        });
    }
});

/**
 * 回调辅助函数，将 Clawdbot 的中间结果或最终结果发回 Python 主应用
 * @param {string} sessionId - 会话 ID
 * @param {string} content - 需要回复给用户的内容
 */
function sendCallback(sessionId, content) {
    console.log(`[CALLBACK] Sending segment for ${sessionId}: ${content.substring(0, 30)}...`);
    const data = JSON.stringify({
        session_id: sessionId,
        content: content
    });

    const url = new URL(CALLBACK_URL);
    const options = {
        hostname: url.hostname,
        port: url.port,
        path: url.pathname,
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(data)
        }
    };

    const request = http.request(options, (response) => {
        console.log(`[CALLBACK] Response status: ${response.statusCode} for ${sessionId}`);
        response.on('data', () => { }); // Consume data
    });

    request.setTimeout(5000);

    request.on('error', (error) => {
        console.error(`[CALLBACK] Error: ${error.message} for ${sessionId}`);
    });

    request.on('timeout', () => {
        console.error(`[CALLBACK] Timeout for ${sessionId}`);
        request.destroy();
    });

    request.write(data);
    request.end();
}

// 启动服务
async function main() {
    console.log(`🔌 正在连接 Gateway (${GATEWAY_URL})...`);

    // 先建立 WebSocket 连接
    try {
        await Promise.race([
            gatewayClient.start(),
            new Promise((_, reject) => setTimeout(() => reject(new Error('连接超时')), 10000))
        ]);
        console.log(`✅ Gateway 连接就绪`);
    } catch (err) {
        console.warn(`⚠️  Gateway 初始连接失败: ${err.message}，服务将在后台重试`);
    }

    // 启动 HTTP 服务
    app.listen(port, () => {
        console.log(`🤖 Clawdbot HTTP Wrapper (WebSocket 模式) 正在监听端口 ${port}`);
        console.log(`   Health: http://localhost:${port}/health`);
        console.log(`   Chat:   http://localhost:${port}/chat (POST)`);
        console.log(`   Gateway: ${GATEWAY_URL}`);
    });
}

main().catch(err => {
    console.error(`启动失败: ${err.message}`);
    process.exit(1);
});

module.exports = app;
