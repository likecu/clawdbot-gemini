const express = require('express');
const cors = require('cors');
const { GoogleGenerativeAI } = require('@google/generative-ai');
require('dotenv').config();

const app = express();
app.use(cors());
app.use(express.json());

const PORT = process.env.PORT || 8081;
const GEMINI_API_KEY = process.env.GOOGLE_API_KEY;

const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);

function toOpenAIFormat(geminiResponse) {
  return {
    id: 'chatcmpl-' + Date.now(),
    object: 'chat.completion',
    created: Math.floor(Date.now() / 1000),
    model: geminiResponse.model || 'gemini-1.5-pro',
    choices: [
      {
        index: 0,
        message: {
          role: 'assistant',
          content: geminiResponse.text(),
        },
        finish_reason: 'stop',
      },
    ],
    usage: {
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
    },
  };
}

app.get('/v1/models', async (req, res) => {
  res.json({
    object: 'list',
    data: [
      { id: 'gemini-2.5-flash', object: 'model', created: Date.now() / 1000, owned_by: 'google' },
      { id: 'gemini-2.5-pro', object: 'model', created: Date.now() / 1000, owned_by: 'google' },
      { id: 'gemini-2.0-flash', object: 'model', created: Date.now() / 1000, owned_by: 'google' },
    ],
  });
});

app.post('/v1/chat/completions', async (req, res) => {
  try {
    const { model, messages, temperature, max_tokens } = req.body;
    
    const modelName = model || 'gemini-2.5-flash';
    
    let geminiModel;
    try {
      geminiModel = genAI.getGenerativeModel({ model: modelName });
    } catch (modelError) {
      geminiModel = genAI.getGenerativeModel({ model: 'gemini-2.0-flash' });
    }

    const lastMessage = messages[messages.length - 1];
    const prompt = typeof lastMessage.content === 'string' 
      ? lastMessage.content 
      : lastMessage.content.map(c => c.text || c).join('\n');

    const result = await geminiModel.generateContent(prompt);
    const response = result.response;

    const openAIResponse = {
      id: 'chatcmpl-' + Date.now(),
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: model || 'gemini-1.5-pro',
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: response.text(),
          },
          finish_reason: 'stop',
        },
      ],
      usage: {
        prompt_tokens: prompt.length / 4,
        completion_tokens: response.text().length / 4,
        total_tokens: (prompt.length + response.text().length) / 4,
      },
    };

    res.json(openAIResponse);
  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({ error: { message: error.message } });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`OpenCode API Server running on port ${PORT}`);
});
