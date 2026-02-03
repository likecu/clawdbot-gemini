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

// Health check
app.get('/health', (req, res) => {
    res.json({ status: 'ok', service: 'clawdbot-http-wrapper' });
});

// POST /chat - Send message to clawdbot and get response
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
            // Debug buffer
            console.log(`[DEBUG] Final stdout buffer length: ${stdoutBuffer.length}`);
            if (stdoutBuffer.length > 500) {
                console.log(`[DEBUG] Final stdout buffer (end): ${stdoutBuffer.slice(-500)}`);
            } else {
                console.log(`[DEBUG] Final stdout buffer: ${stdoutBuffer}`);
            }

            // Brace counting to find first valid JSON object
            let jsonStart = stdoutBuffer.indexOf('{');
            let jsonEnd = -1;

            if (jsonStart !== -1) {
                let braceCount = 0;
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
            }

            console.log(`[DEBUG] JSON start index: ${jsonStart}, calculated end index: ${jsonEnd}`);

            if (jsonStart !== -1 && jsonEnd !== -1) {
                const jsonStr = stdoutBuffer.substring(jsonStart, jsonEnd + 1);
                const result = JSON.parse(jsonStr);

                if (result) {
                    console.log(`[DEBUG] Parsed JSON keys: ${Object.keys(result)}`);
                    if (result.result) {
                        console.log(`[DEBUG] result.result keys: ${Object.keys(result.result)}`);
                    }

                    // Support payloads at root OR nested in result
                    const payloads = result.payloads || (result.result && result.result.payloads);

                    if (payloads) {
                        payloads.forEach(p => {
                            if (p.text) {
                                sendCallback(sessionId, p.text);
                                sentCount++;
                                finalReply = p.text; // Keep last as final reply
                            }
                        });
                    }
                } else {
                    console.error("No JSON found in stdout");
                }
            }
        } catch (e) {
            console.error(`Error parsing JSON output: ${e.message}`);
        }

        res.json({
            reply: finalReply,
            segments_sent: sentCount,
        });
    });
});

// Helper to send data back to the Python app
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

app.listen(port, () => {
    console.log(`🤖 Clawdbot HTTP Wrapper listening on port ${port}`);
    console.log(`Health endpoint: http://localhost:${port}/health`);
    console.log(`Chat endpoint: http://localhost:${port}/chat (POST)`);
    console.log(`Sessions directory: ${SESSIONS_DIR}`);
});

module.exports = app;
