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

// Get latest assistant reply from a session file
function getLatestReply(sessionFile) {
    try {
        const content = fs.readFileSync(sessionFile, 'utf8');
        const lines = content.trim().split('\n');

        // Read lines in reverse to find the latest assistant message
        for (let i = lines.length - 1; i >= 0; i--) {
            try {
                const line = JSON.parse(lines[i]);
                if (line.type === 'message' &&
                    line.message &&
                    line.message.role === 'assistant' &&
                    line.message.content &&
                    line.message.content.length > 0) {
                    // Extract text from content
                    const textContent = line.message.content.find(c => c.type === 'text');
                    if (textContent && textContent.text) {
                        return textContent.text;
                    }
                }
            } catch (parseError) {
                // Skip invalid JSON lines
                continue;
            }
        }
        return null;
    } catch (error) {
        console.error(`Error reading session file: ${error.message}`);
        return null;
    }
}

// Find the most recently modified .jsonl file (excluding deleted files)
function findLatestSessionFile() {
    try {
        const files = fs.readdirSync(SESSIONS_DIR)
            .filter(f => f.endsWith('.jsonl') && !f.includes('.deleted'))
            .map(f => ({
                name: f,
                path: path.join(SESSIONS_DIR, f),
                mtime: fs.statSync(path.join(SESSIONS_DIR, f)).mtime
            }))
            .sort((a, b) => b.mtime - a.mtime);

        return files.length > 0 ? files[0].path : null;
    } catch (error) {
        console.error(`Error finding session files: ${error.message}`);
        return null;
    }
}

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
        '--timeout', '180'
    ];

    console.log(`[${new Date().toISOString()}] DEBUG: Initializing stats...`);
    let currentStats = findLatestSessionFileStats();
    console.log(`[${new Date().toISOString()}] DEBUG: currentStats=${JSON.stringify(currentStats)}`);

    let sentSegments = new Set();

    console.log(`[${new Date().toISOString()}] DEBUG: Spawning clawdbot...`);
    const clawdbot = spawn('/home/milk/.npm-global/bin/clawdbot', cmdArgs, {
        env: { ...process.env, PATH: `/home/milk/.npm-global/bin:${process.env.PATH}` }
    });

    clawdbot.on('error', (err) => {
        console.error(`[${new Date().toISOString()}] SPAWN ERROR: ${err.message}`);
    });

    let stdout = '';
    let stderr = '';

    clawdbot.stdout.on('data', (data) => {
        stdout += data;
        console.log(`[STDOUT] ${data.toString().substring(0, 50)}...`);
    });
    clawdbot.stderr.on('data', (data) => {
        stderr += data;
        console.log(`[STDERR] ${data.toString().substring(0, 50)}...`);
    });

    console.log(`[${new Date().toISOString()}] DEBUG: Setting poll interval...`);
    const pollInterval = setInterval(() => {
        try {
            const latestFile = findLatestSessionFileStats();
            if (latestFile) {
                const { segments, lastReadSize } = extractNewSegments(latestFile.path, currentStats);

                if (segments.length > 0) {
                    segments.forEach(seg => {
                        if (!sentSegments.has(seg)) {
                            console.log(`[${new Date().toISOString()}] Pushing segment: ${seg.substring(0, 20)}...`);
                            sendCallback(sessionId, seg);
                            sentSegments.add(seg);
                        }
                    });
                }
                currentStats = { ...latestFile, size: lastReadSize };
            }
        } catch (pollErr) {
            console.error(`[POLL ERROR] ${pollErr.message}`);
        }
    }, 1500);

    clawdbot.on('close', (code) => {
        clearInterval(pollInterval);
        console.log(`[${new Date().toISOString()}] Clawdbot process finished with code ${code}`);

        setTimeout(() => {
            try {
                const latestFile = findLatestSessionFileStats();
                if (latestFile) {
                    const { segments } = extractNewSegments(latestFile.path, currentStats);
                    segments.forEach(seg => {
                        if (!sentSegments.has(seg)) {
                            sendCallback(sessionId, seg);
                            sentSegments.add(seg);
                        }
                    });
                }
            } catch (finalPollErr) {
                console.error(`[FINAL POLL ERROR] ${finalPollErr.message}`);
            }

            console.log(`[${new Date().toISOString()}] Sending JSON response to client`);
            res.json({
                reply: Array.from(sentSegments).pop() || "任务已完成。",
                segments_sent: sentSegments.size,
                is_callback_mode: true
            });
        }, 1000);
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

function findLatestSessionFileStats() {
    try {
        const files = fs.readdirSync(SESSIONS_DIR)
            .filter(f => f.endsWith('.jsonl') && !f.includes('.deleted'))
            .map(f => {
                const fullPath = path.join(SESSIONS_DIR, f);
                const stats = fs.statSync(fullPath);
                return { name: f, path: fullPath, size: stats.size, mtime: stats.mtime };
            })
            .sort((a, b) => b.mtime - a.mtime);
        return files.length > 0 ? files[0] : null;
    } catch (error) {
        return null;
    }
}

function extractNewSegments(filePath, beforeStats) {
    try {
        const stats = fs.statSync(filePath);
        const startOffset = (beforeStats && beforeStats.path === filePath) ? beforeStats.size : 0;

        if (stats.size <= startOffset) return { segments: [], lastReadSize: startOffset };

        const buffer = Buffer.alloc(stats.size - startOffset);
        const fd = fs.openSync(filePath, 'r');
        fs.readSync(fd, buffer, 0, buffer.length, startOffset);
        fs.closeSync(fd);

        const newRawContent = buffer.toString('utf8');
        const lastNewLineIndex = newRawContent.lastIndexOf('\n');

        if (lastNewLineIndex === -1) {
            // No complete line yet
            return { segments: [], lastReadSize: startOffset };
        }

        // Exactly the bytes that form complete lines
        const completeText = newRawContent.substring(0, lastNewLineIndex + 1);
        const completeBytes = Buffer.byteLength(completeText);
        const completeLines = completeText.split(/\r?\n/);

        const newSegments = [];
        for (const lineStr of completeLines) {
            if (!lineStr.trim()) continue;
            try {
                const line = JSON.parse(lineStr);
                if (line.type !== 'message' || !line.message) continue;

                const role = line.message.role;
                const contentParts = line.message.content || [];

                if (role === 'assistant') {
                    contentParts.forEach(p => {
                        if (p.type === 'text' && p.text.trim()) {
                            newSegments.push(p.text.trim());
                        }
                        if (p.type === 'toolCall') {
                            newSegments.push(`🛠️ **正在执行: ${p.name}**\n参数: \`${JSON.stringify(p.arguments)}\``);
                        }
                    });
                } else if (role === 'toolResult') {
                    contentParts.forEach(p => {
                        if (p.type === 'text' && p.text.trim()) {
                            let t = p.text.trim();
                            if (t.length > 800) t = t.substring(0, 800) + '... (结果过长已截断)';
                            newSegments.push(`✅ **执行结果:**\n\`\`\`\n${t}\n\`\`\``);
                        }
                    });
                }
            } catch (e) {
                console.log(`[DEBUG] Partial or invalid JSON skipped: ${lineStr.substring(0, 20)}...`);
            }
        }

        return {
            segments: newSegments,
            lastReadSize: startOffset + completeBytes
        };
    } catch (error) {
        console.error(`Error in extractNewSegments: ${error.message}`);
        return { segments: [], lastReadSize: beforeStats ? beforeStats.size : 0 };
    }
}

app.listen(port, () => {
    console.log(`🤖 Clawdbot HTTP Wrapper listening on port ${port}`);
    console.log(`Health endpoint: http://localhost:${port}/health`);
    console.log(`Chat endpoint: http://localhost:${port}/chat (POST)`);
    console.log(`Sessions directory: ${SESSIONS_DIR}`);
});

module.exports = app;
