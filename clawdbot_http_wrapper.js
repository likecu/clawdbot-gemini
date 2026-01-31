#!/usr/bin/env node

/**
 * Clawdbot HTTP Wrapper
 * Provides HTTP API for calling clawdbot CLI and extracting responses from session files
 */

const express = require('express');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const bodyParser = require('body-parser');

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

    const sessionId = session_id || 'qq_default';
    const cmd = `export PATH=/home/milk/.npm-global/bin:$PATH && clawdbot agent --to "${sessionId}" --message "${message.replace(/"/g, '\\"')}" --timeout 30 2>&1`;

    console.log(`[${new Date().toISOString()}] Processing request: ${message.substring(0, 50)}...`);

    // Record the current latest file before running clawdbot
    const beforeFile = findLatestSessionFile();
    const beforeTime = new Date();

    exec(cmd, { maxBuffer: 1024 * 1024 * 10 }, (error, stdout, stderr) => {
        if (error && !stdout.includes('Completed turn')) {
            console.error(`Error executing clawdbot: ${error.message}`);
            return res.status(500).json({
                error: 'Failed to execute clawdbot',
                details: error.message
            });
        }

        // Wait a bit for file to be fully written
        setTimeout(() => {
            try {
                // Find the session file (either the same one or a new one)
                const latestFile = findLatestSessionFile();

                if (!latestFile) {
                    console.error('No session files found');
                    return res.status(500).json({
                        error: 'No session files found',
                        reply: '抱歉，无法找到会话文件。'
                    });
                }

                // Get the latest reply from the session file
                const reply = getLatestReply(latestFile);

                if (reply) {
                    console.log(`[${new Date().toISOString()}] Response: ${reply.substring(0, 100)}...`);
                    return res.json({ reply: reply });
                } else {
                    console.warn('Could not extract reply from session file');
                    return res.json({ reply: '收到消息，但无法提取回复内容。' });
                }
            } catch (extractError) {
                console.error(`Error extracting reply: ${extractError.message}`);
                return res.status(500).json({
                    error: 'Failed to extract reply',
                    details: extractError.message,
                    reply: '抱歉，提取回复时出错。'
                });
            }
        }, 500); // Wait 500ms for file to be written
    });
});

app.listen(port, () => {
    console.log(`🤖 Clawdbot HTTP Wrapper listening on port ${port}`);
    console.log(`Health endpoint: http://localhost:${port}/health`);
    console.log(`Chat endpoint: http://localhost:${port}/chat (POST)`);
    console.log(`Sessions directory: ${SESSIONS_DIR}`);
});

module.exports = app;
