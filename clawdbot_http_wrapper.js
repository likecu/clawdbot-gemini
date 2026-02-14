#!/usr/bin/env node

/**
 * Clawdbot HTTP Wrapper
 * Provides HTTP API for calling clawdbot CLI and extracting responses from session files
 */

const express = require('express');
const { exec, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');
const bodyParser = require('body-parser');

const CALLBACK_URL = process.env.CALLBACK_URL || 'http://127.0.0.1:8081/api/clawdbot/callback';

const app = express();
const port = 3009;

app.use(bodyParser.json());

// Path to clawdbot sessions
const SESSIONS_DIR = path.join(os.homedir(), '.clawdbot/agents/main/sessions');

// 健康检查接口，用于验证服务是否正常运行
app.get('/health', (req, res) => {
    res.json({ status: 'ok', service: 'clawdbot-http-wrapper' });
});

/**
 * 处理聊天请求的 POST 接口
 * 接收用户消息并启动 clawdbot CLI 进行处理
 * @param {Object} req.body.message - 用户输入的消息内容
 * @param {Object} req.body.session_id - 会话唯一标识符
 */
app.post('/chat', async (req, res) => {
    const { message, session_id } = req.body;

    if (!message) {
        return res.status(400).json({ error: 'Message is required' });
    }

    console.log(`[${new Date().toISOString()}] DEBUG: Entering /chat handler`);
    const sessionId = session_id || 'qq_default';
    console.log(`[${new Date().toISOString()}] DEBUG: SessionID=${sessionId}, Message=${message?.substring(0, 30)}...`);

    const enrichedMessage = `${message}\n\n(Note: You have FULL access to tools. Please use the 'exec' tool to run Python scripts or other commands to get actual results. Do NOT simulate execution.)`;

    const cmdArgs = [
        'agent',
        '--to', sessionId,
        '--message', enrichedMessage,
        '--deliver',
        '--thinking', 'high',
        '--verbose', 'on',
        '--timeout', '180',
        '--json'
    ];

    let stdoutBuffer = '';

    console.log(`[${new Date().toISOString()}] DEBUG: Spawning clawdbot...`);
    const clawdbot = spawn('/home/milk/.npm-global/bin/clawdbot', cmdArgs, {
        env: { ...process.env, PATH: `/home/milk/.npm-global/bin:${process.env.PATH}` }
    });

    clawdbot.on('error', (err) => {
        console.error(`[${new Date().toISOString()}] SPAWN ERROR: ${err.message}`);
    });

    clawdbot.stdout.on('data', (data) => {
        const chunk = data.toString();
        stdoutBuffer += chunk;
        console.log(`[STDOUT] ${chunk.substring(0, 50)}...`);
    });

    clawdbot.stderr.on('data', (data) => {
        console.log(`[STDERR] ${data.toString().substring(0, 50)}...`);
    });

    clawdbot.on('close', (code) => {
        console.log(`[${new Date().toISOString()}] Clawdbot process finished with code ${code}`);

        let sentCount = 0;
        let finalReply = "任务已完成。";

        try {
            // Iterate through all potential JSON objects in the buffer
            let currentIdx = 0;
            while (true) {
                let jsonStart = stdoutBuffer.indexOf('{', currentIdx);
                if (jsonStart === -1) break;

                let braceCount = 0;
                let jsonEnd = -1;
                for (let i = jsonStart; i < stdoutBuffer.length; i++) {
                    if (stdoutBuffer[i] === '{') {
                        braceCount++;
                    } else if (stdoutBuffer[i] === '}') {
                        braceCount--;
                        if (braceCount === 0) {
                            jsonEnd = i;
                            break;
                        }
                    }
                }

                if (jsonEnd !== -1) {
                    const jsonStr = stdoutBuffer.substring(jsonStart, jsonEnd + 1);
                    try {
                        const result = JSON.parse(jsonStr);
                        console.log(`[DEBUG] Parsed JSON from buffer at ${jsonStart}`);

                        const payloads = result.payloads || (result.result && result.result.payloads);

                        if (payloads) {
                            payloads.forEach(p => {
                                if (p.text) {
                                    sendCallback(sessionId, p.text);
                                    sentCount++;
                                    finalReply = p.text;
                                }
                            });
                        }
                    } catch (parseErr) {
                        console.error(`[DEBUG] Failed to parse JSON object at ${jsonStart}: ${parseErr.message}`);
                    }
                    currentIdx = jsonEnd + 1;
                } else {
                    break;
                }
            }
        } catch (e) {
            console.error(`Error processing stdout buffer: ${e.message}`);
        }

        res.json({
            reply: finalReply,
            segments_sent: sentCount,
            is_callback_mode: sentCount > 0,
            stdout_preview: stdoutBuffer.substring(0, 100)
        });
    });
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

    request.setTimeout(5000); // 5s timeout for callback

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

// 启动 Express 服务器，监听指定端口
app.listen(port, () => {
    console.log(`🤖 Clawdbot HTTP Wrapper 正在监听端口 ${port}`);
    console.log(`Health endpoint: http://localhost:${port}/health`);
    console.log(`Chat endpoint: http://localhost:${port}/chat (POST)`);
    console.log(`Sessions directory: ${SESSIONS_DIR}`);
});

module.exports = app;
