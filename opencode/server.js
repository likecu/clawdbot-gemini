const express = require('express');
const cors = require('cors');
const { GoogleGenerativeAI } = require('@google/generative-ai');
const fetch = require('node-fetch');
require('dotenv').config();

const app = express();
app.use(cors());
app.use(express.json());

const PORT = process.env.PORT || 8080;

const GEMINI_API_KEY = process.env.GOOGLE_API_KEY;
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
const OPENROUTER_API_BASE_URL = process.env.OPENROUTER_API_BASE_URL || 'https://openrouter.ai/api/v1';

const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);

function isGeminiModel(modelName) {
  return modelName && (modelName.startsWith('gemini-') || modelName.startsWith('gemma-'));
}

function isOpenRouterModel(modelName) {
  return modelName && (
    modelName.startsWith('deepseek/') ||
    modelName.startsWith('anthropic/') ||
    modelName.startsWith('openai/') ||
    modelName.startsWith('meta/') ||
    !isGeminiModel(modelName)
  );
}

async function callGemini(modelName, prompt) {
  let geminiModel;
  try {
    geminiModel = genAI.getGenerativeModel({ model: modelName });
  } catch (modelError) {
    geminiModel = genAI.getGenerativeModel({ model: 'gemini-2.0-flash' });
  }

  const result = await geminiModel.generateContent(prompt);
  return result.response.text();
}

async function callOpenRouter(modelName, messages, temperature, max_tokens) {
  const response = await fetch(`${OPENROUTER_API_BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
      'Content-Type': 'application/json',
      'HTTP-Referer': 'http://localhost:8080',
      'X-Title': 'OpenCode API Server',
    },
    body: JSON.stringify({
      model: modelName,
      messages: messages,
      temperature: temperature || 0.7,
      max_tokens: max_tokens || 4096,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`OpenRouter API error: ${error}`);
  }

  const data = await response.json();
  return data.choices[0].message.content;
}

app.get('/v1/models', async (req, res) => {
  res.json({
    object: 'list',
    data: [
      { id: 'gemini-2.5-flash', object: 'model', created: Math.floor(Date.now() / 1000), owned_by: 'google' },
      { id: 'gemini-2.5-pro', object: 'model', created: Math.floor(Date.now() / 1000), owned_by: 'google' },
      { id: 'gemini-2.0-flash', object: 'model', created: Math.floor(Date.now() / 1000), owned_by: 'google' },
      { id: 'deepseek/deepseek-r1', object: 'model', created: Math.floor(Date.now() / 1000), owned_by: 'deepseek' },
      { id: 'deepseek/deepseek-chat', object: 'model', created: Math.floor(Date.now() / 1000), owned_by: 'deepseek' },
    ],
  });
});

app.post('/v1/chat/completions', async (req, res) => {
  try {
    const { model, messages, temperature, max_tokens } = req.body;

    const modelName = model || 'deepseek/deepseek-r1';

    const lastMessage = messages[messages.length - 1];
    const prompt = typeof lastMessage.content === 'string'
      ? lastMessage.content
      : lastMessage.content.map(c => c.text || c).join('\n');

    let content;
    let provider = 'unknown';
    let usedProvider = null;

    if (isGeminiModel(modelName) && GEMINI_API_KEY) {
      try {
        content = await callGemini(modelName, prompt);
        provider = 'google';
        usedProvider = 'google';
      } catch (geminiError) {
        console.log(`[Fallback] Gemini failed for ${modelName}, falling back to OpenRouter`);
        if (OPENROUTER_API_KEY) {
          content = await callOpenRouter('deepseek/deepseek-r1', messages, temperature, max_tokens);
          provider = 'openrouter';
          usedProvider = 'openrouter (fallback)';
        } else {
          throw geminiError;
        }
      }
    } else if (isOpenRouterModel(modelName) && OPENROUTER_API_KEY) {
      content = await callOpenRouter(modelName, messages, temperature, max_tokens);
      provider = 'openrouter';
      usedProvider = 'openrouter';
    } else {
      content = await callGemini('gemini-2.0-flash', prompt);
      provider = 'google-fallback';
      usedProvider = 'google-fallback';
    }

    const openAIResponse = {
      id: 'chatcmpl-' + Date.now(),
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: modelName,
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: content,
          },
          finish_reason: 'stop',
        },
      ],
      usage: {
        prompt_tokens: prompt.length / 4,
        completion_tokens: content.length / 4,
        total_tokens: (prompt.length + content.length) / 4,
      },
    };

    console.log(`[${usedProvider || provider}] Model: ${modelName}, Prompt length: ${prompt.length}, Response length: ${content.length}`);
    res.json(openAIResponse);
  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({ error: { message: error.message } });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', provider: 'opencode' });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`OpenCode API Server running on port ${PORT}`);
  console.log(`Supports: Gemini models, OpenRouter models (deepseek, anthropic, openai, etc.)`);
});
