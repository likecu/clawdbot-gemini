const express = require('express');
const cors = require('cors');
const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = require('@modelcontextprotocol/sdk/client/stdio.js');
const fetch = require('node-fetch');
require('dotenv').config();

const app = express();
app.use(cors());
app.use(express.json());

const PORT = process.env.PORT || 8080;

const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
const OPENROUTER_API_BASE_URL = process.env.OPENROUTER_API_BASE_URL || 'https://openrouter.ai/api/v1';
const DEFAULT_MODEL = process.env.OPENROUTER_DEFAULT_MODEL || 'deepseek/deepseek-r1';

let mcpClients = {};
let mcpTools = [];

async function createStdioMCPClient(name, command, args = [], env = {}) {
  const transport = new StdioClientTransport({
    command,
    args,
    env: { ...process.env, ...env }
  });

  const client = new Client({
    name: `opencode-${name}`,
    version: '1.0.0'
  });

  await client.connect(transport);
  return client;
}

async function initializeMCPServers() {
  console.log('[MCP] 初始化 MCP 服务器...');
  const mcpConfig = process.env.MCP_SERVERS || '';
  
  if (!mcpConfig) {
    console.log('[MCP] 未配置 MCP 服务器');
    return;
  }

  const servers = mcpConfig.split(',').map(s => s.trim()).filter(s => s);

  for (const serverConfig of servers) {
    const [name, command, ...args] = serverConfig.split(' ');
    
    if (!command) {
      console.log(`[MCP] 跳过配置错误的服务器: ${serverConfig}`);
      continue;
    }

    try {
      console.log(`[MCP] 启动服务器: ${name} (${command})`);
      const client = await createStdioMCPClient(name, command, args);
      
      const toolsResult = await client.listTools();
      mcpTools.push(...toolsResult.tools.map(tool => ({
        type: 'function',
        function: {
          name: tool.name,
          description: tool.description || '',
          parameters: {
            type: 'object',
            properties: (tool.inputSchema?.properties || {}),
            required: tool.inputSchema?.required || []
          }
        }
      })));

      mcpClients[name] = { client, tools: toolsResult.tools };
      console.log(`[MCP] ${name} 已启动，工具数量: ${toolsResult.tools.length}`);
    } catch (error) {
      console.error(`[MCP] 启动 ${name} 失败: ${error.message}`);
    }
  }

  console.log(`[MCP] 初始化完成，总工具数量: ${mcpTools.length}`);
}

async function callMCPTool(serverName, toolName, arguments_) {
  const server = mcpClients[serverName];
  if (!server) {
    throw new Error(`MCP 服务器 ${serverName} 未找到`);
  }

  const result = await server.client.callTool({
    name: toolName,
    arguments: arguments_
  });

  return result.content.map(c => {
    if (c.type === 'text') return c.text;
    if (c.type === 'image') return `[Image: ${c.data}]`;
    return JSON.stringify(c);
  }).join('\n');
}

async function callOpenRouter(modelName, messages, temperature, max_tokens, tools = null) {
  const openrouterTools = tools?.map(tool => ({
    type: 'function',
    function: {
      name: tool.function.name,
      description: tool.function.description,
      parameters: tool.function.parameters
    }
  })) || [];

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
      tools: openrouterTools.length > 0 ? openrouterTools : undefined,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`OpenRouter API error: ${error}`);
  }

  const data = await response.json();
  return {
    text: () => data.choices[0].message.content,
    functionCalls: data.choices[0].message.tool_calls || []
  };
}

app.get('/v1/models', async (req, res) => {
  res.json({
    object: 'list',
    data: [
      { id: 'deepseek/deepseek-r1', object: 'model', created: Math.floor(Date.now() / 1000), owned_by: 'deepseek' },
      { id: 'deepseek/deepseek-chat', object: 'model', created: Math.floor(Date.now() / 1000), owned_by: 'deepseek' },
      { id: 'anthropic/claude-3.5-sonnet', object: 'model', created: Math.floor(Date.now() / 1000), owned_by: 'anthropic' },
      { id: 'openai/gpt-4o', object: 'model', created: Math.floor(Date.now() / 1000), owned_by: 'openai' },
    ],
  });
});

app.get('/v1/tools', async (req, res) => {
  res.json({
    object: 'list',
    data: mcpTools,
  });
});

app.post('/v1/chat/completions', async (req, res) => {
  try {
    const { model, messages, temperature, max_tokens, tools: providedTools } = req.body;

    const modelName = model || DEFAULT_MODEL;

    const lastMessage = messages[messages.length - 1];
    const prompt = typeof lastMessage.content === 'string'
      ? lastMessage.content
      : lastMessage.content.map(c => c.text || c).join('\n');

    const availableTools = mcpTools.length > 0 ? mcpTools : providedTools;

    if (!OPENROUTER_API_KEY) {
      throw new Error('未配置 OPENROUTER_API_KEY');
    }

    let content;
    let usedProvider = 'openrouter';

    const response = await callOpenRouter(modelName, messages, temperature, max_tokens, availableTools);
    
    if (response.functionCalls && response.functionCalls.length > 0) {
      console.log(`[MCP] OpenRouter 调用工具: ${response.functionCalls.map(c => c.function.name).join(', ')}`);
      
      for (const call of response.functionCalls) {
        const [serverName, toolName] = call.function.name.split('::');
        if (serverName && toolName) {
          try {
            const toolResult = await callMCPTool(serverName, toolName, call.function.arguments || {});
            messages.push({
              role: 'assistant',
              content: null,
              tool_calls: [call]
            });
            messages.push({
              role: 'tool',
              content: toolResult,
              tool_call_id: call.id
            });
          } catch (toolError) {
            console.error(`[MCP] 工具调用失败: ${toolError.message}`);
            messages.push({
              role: 'tool',
              content: `工具调用失败: ${toolError.message}`,
              tool_call_id: call.id
            });
          }
        }
      }

      const secondResponse = await callOpenRouter(modelName, messages, temperature, max_tokens, availableTools);
      content = secondResponse.text();
      usedProvider = 'openrouter+mcp';
    } else {
      content = response.text();
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

    console.log(`[${usedProvider}] Model: ${modelName}, MCP Tools: ${mcpTools.length}, Response length: ${content.length}`);
    res.json(openAIResponse);
  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({ error: { message: error.message } });
  }
});

app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    provider: 'opencode',
    defaultModel: DEFAULT_MODEL,
    mcpServers: Object.keys(mcpClients),
    mcpToolsCount: mcpTools.length
  });
});

app.listen(PORT, '0.0.0.0', async () => {
  console.log(`OpenCode API Server running on port ${PORT}`);
  console.log(`Default model: ${DEFAULT_MODEL}`);
  await initializeMCPServers();
});
