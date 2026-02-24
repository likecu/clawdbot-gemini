// Enhanced QQ-Clawdbot Integration Script
// With proper response handling from Clawdbot

const WebSocket = require('ws');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

class EnhancedQQClawdbotBridge {
  /**
   * 初始化 EnhancedQQClawdbotBridge 实例。
   * 设置 OneBot API 端点、NapCat 访问令牌、WebSocket 地址以及底层连接状态。
   * 同时启动 WebSocket 连接。
   */
  constructor() {
    this.onebotEndpoint = 'http://localhost:3000';
    this.accessToken = process.env.NAPCAT_ACCESS_TOKEN || 'YOUR_NAPCAT_ACCESS_TOKEN';
    this.wsUrl = 'ws://localhost:8080';
    this.ws = null;
    this.connected = false;

    // Track message mappings for responses
    this.messageMap = new Map();

    console.log('🚀 Starting Enhanced QQ-Clawdbot Bridge...');
    this.connectWebSocket();
  }

  /**
   * 建立与 QQ (NapCat) 的 WebSocket 连接。
   * 处理连接建立、消息接收、连接关闭及错误事件。
   * 断线时自动尝试在 5 秒后重连。
   */
  connectWebSocket() {
    console.log(`🔗 Connecting to: ${this.wsUrl}`);

    try {
      this.ws = new WebSocket(this.wsUrl);

      this.ws.on('open', () => {
        console.log('✅ Successfully connected to QQ WebSocket!');
        this.connected = true;
        console.log('🤖 Enhanced QQ-Clawdbot bridge is now operational');
      });

      this.ws.on('message', (data) => {
        try {
          const message = JSON.parse(data.toString());
          this.handleQQMessage(message);
        } catch (error) {
          console.error('Error parsing message:', error);
        }
      });

      this.ws.on('close', (code, reason) => {
        this.connected = false;
        console.log(`🔗 Connection closed. Code: ${code}, Reason: ${reason || 'No reason'}`);
        console.log('🔄 Attempting to reconnect in 5 seconds...');
        setTimeout(() => this.connectWebSocket(), 5000);
      });

      this.ws.on('error', (error) => {
        console.error('❌ WebSocket error:', error.message);
      });
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setTimeout(() => this.connectWebSocket(), 5000);
    }
  }

  /**
   * 处理接收到的 QQ 消息/事件。
   * 过滤掉自身发送的回显消息，并根据不同消息类型（普通消息、群通知、好友请求、元事件等）分发给具体的处理函数。
   *
   * @param {Object} message - 从 QQ WebSocket 接收到的事件数据对象
   */
  async handleQQMessage(message) {
    // Check if this is a response to our action (has echo field)
    if (message.echo && message.echo.includes('clawdbot_response_')) {
      // This is a confirmation that our response was sent, ignore
      return;
    }

    console.log('📥 Received QQ message:', {
      post_type: message.post_type,
      user_id: message.user_id,
      raw_message: message.raw_message
    });

    // Process different types of messages
    switch (message.post_type) {
      case 'message':
        await this.processMessage(message);
        break;
      case 'notice':
        // Only log important notices, ignore typing indicators
        if (!message.sub_type?.includes('input_status')) {
          console.log('📢 Notice received:', message);
        }
        break;
      case 'request':
        console.log('📨 Request received:', message);
        if (message.request_type === 'friend') {
          await this.approveFriendRequest(message.flag);
        }
        break;
      case 'meta_event':
        if (message.meta_event_type === 'lifecycle' && message.sub_type === 'connect') {
          console.log('🔄 WebSocket reconnected');
        }
        break;
      default:
        console.log('❓ Unknown message type:', message);
    }
  }

  /**
   * 处理用户发送的普通消息（私聊或群聊）。
   * 解析消息内容，提取发送者身份（昵称或QQ号），将身份信息拼接到消息前缀，
   * 记录消息映射以便回复时使用，并转发给 Clawdbot 核心进行处理。
   *
   * @param {Object} message - 用户发送的普通消息对象
   */
  async processMessage(message) {
    const userId = message.user_id;
    const groupId = message.group_id || null;
    const rawMessage = message.raw_message || '';
    const messageArray = message.message || [];

    // 提取发送者名称（群昵称或 QQ 昵称，默认使用 QQ 号）
    const senderName = message.sender?.card || message.sender?.nickname || userId;

    // Parse the actual message content from array format
    let msgContent = '';
    if (Array.isArray(messageArray)) {
      msgContent = messageArray.map(item => {
        if (item.type === 'text') {
          return item.data.text || '';
        } else if (item.type === 'image') {
          return '[图片]';
        } else if (item.type === 'at') {
          return `@${item.data.text || item.data.qq}`;
        } else {
          return `[${item.type}]`;
        }
      }).join('');
    } else {
      msgContent = rawMessage;
    }

    // 将发送者身份前置到消息内容中
    msgContent = `[${senderName}]: ${msgContent}`;

    console.log(`💬 Message from QQ ${userId} (${senderName}): ${msgContent}`);

    // Store message info for response mapping
    const messageId = `qq_${Date.now()}_${userId}_${groupId || 'private'}`;
    this.messageMap.set(messageId, {
      userId: userId,
      groupId: groupId,
      originalMessage: msgContent,
      timestamp: Date.now()
    });

    // Clean up old mappings to prevent memory leaks
    setTimeout(() => {
      this.messageMap.delete(messageId);
    }, 300000); // 5 minutes

    // Determine if it's a group or private message
    if (groupId) {
      console.log(`👥 Group message from ${groupId}, user ${userId}: ${msgContent}`);

      // Forward the message to Clawdbot for processing using direct session creation
      await this.sendToClawdbotDirect(msgContent, userId, groupId);
    } else {
      console.log(`👤 Private message from user ${userId}: ${msgContent}`);

      // Forward the message to Clawdbot for processing using direct session creation
      await this.sendToClawdbotDirect(msgContent, userId, groupId);
    }
  }

  // Method to send message to Clawdbot for processing using direct session creation
  /**
   * 将经过包装的文本消息直接发送给 Clawdbot 系统处理。
   * 通过调用 `clawdbot agent` 命令，附带特定通道(QQ)、作者ID及目标（群/私聊）ID。
   * 若发生错误，会将错误信息发送回原 QQ 用户/群组。
   *
   * @param {string} message - 带身份前缀的用户消息文本
   * @param {string|number} userId - 发送用户的 QQ 号
   * @param {string|number|null} groupId - 若为群聊则为群号，私聊则为空
   */
  async sendToClawdbotDirect(message, userId, groupId) {
    console.log(`🔄 Forwarding message to Clawdbot for processing: ${message}`);

    try {
      // Get the original message info
      const originalMsgInfo = this.messageMap.get(`qq_${Date.now()}_${userId}_${groupId || 'private'}`);

      // Use Clawdbot CLI to send the message to a specific session
      // We'll use the Clawdbot messaging protocol to ensure correct user mapping and channel routing
      const channel = 'qq'; // Explicitly state the channel name
      const authorId = userId; // The QQ number is the author ID
      const targetId = groupId || userId; // Group ID for groups, User ID for private

      // The message content should be the raw user message for Clawdbot to process naturally
      const msgContentForClawdbot = message.replace(/'/g, '\\"');

      // Use the 'sessions_send' tool logic or an API that correctly passes channel context
      // Since this is a JS bridge, we use the Clawdbot CLI with explicit parameters
      const cmd = `clawdbot agent --channel "${channel}" --author-id "${authorId}" --target-id "${targetId}" --session-id "${targetId}" --message '${msgContentForClawdbot}' --local`;

      console.log(`Executing Clawdbot command: ${cmd}`);

      // Execute the command
      exec(cmd, { timeout: 30000 }, (error, stdout, stderr) => {
        if (error) {
          console.error('Error sending message to Clawdbot:', error);

          // Get the original message info to send error back to user
          if (originalMsgInfo) {
            this.sendQQResponse(`🤖 错误: 无法处理您的消息。请稍后再试。错误信息: ${error.message}`,
              originalMsgInfo.userId, originalMsgInfo.groupId);
          }
          return;
        }

        console.log('Message sent successfully to Clawdbot session:', stdout);

        // Send a temporary acknowledgment to the user
        if (originalMsgInfo) {
          this.sendQQResponse(`🤖 已收到您的消息并转发至AI核心处理: "${originalMsgInfo.originalMessage}"。请稍候。`,
            originalMsgInfo.userId, originalMsgInfo.groupId);
        }
      });
    } catch (error) {
      console.error('Error processing message with Clawdbot:', error);

      // Get the original message info to send error back to user
      const originalMsgInfo = this.messageMap.get(`qq_${Date.now()}_${userId}_${groupId || 'private'}`);
      if (originalMsgInfo) {
        this.sendQQResponse(`🤖 处理您的消息时发生错误: ${error.message}`,
          originalMsgInfo.userId, originalMsgInfo.groupId);
      }
    }
  }

  /**
   * 自动通过传入的好友添加请求。
   *
   * @param {string} flag - 加好友请求的唯一标识符
   */
  async approveFriendRequest(flag) {
    try {
      // Use WebSocket to approve friend request
      const messageData = {
        action: 'set_friend_add_request',
        params: {
          flag: flag,
          approve: true
        },
        echo: `approve_request_${Date.now()}`
      };

      this.ws.send(JSON.stringify(messageData));
      console.log(`✅ Friend request approval sent via WebSocket for flag: ${flag}`);
    } catch (error) {
      console.error('Error approving friend request via WebSocket:', error);
    }
  }

  /**
   * 向发送消息的 QQ 用户或群组返回 Clawdbot 生成的回复。
   * 检查 WebSocket 状态通过 `send_group_msg` 或 `send_private_msg` 将消息投递到 QQ。
   *
   * @param {string} response - 要发送给用户的回复文本
   * @param {string|number} userId - 目标用户的 QQ 号
   * @param {string|number|null} groupId - 目标群号（如果是群聊）
   * @returns {boolean} - 发送成功返回 true，否则 false
   */
  async sendQQResponse(response, userId, groupId) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error('❌ WebSocket not ready for sending message');
      return false;
    }

    try {
      let messageData;
      if (groupId) {
        // Send to group via WebSocket
        messageData = {
          action: 'send_group_msg',
          params: {
            group_id: groupId,
            message: response
          },
          echo: `clawdbot_response_${Date.now()}`
        };
        console.log(`📤 Sending response to group ${groupId} via WebSocket`);
      } else {
        // Send private message via WebSocket
        messageData = {
          action: 'send_private_msg',
          params: {
            user_id: userId,
            message: response
          },
          echo: `clawdbot_response_${Date.now()}`
        };
        console.log(`📤 Sending response to user ${userId} via WebSocket`);
      }

      // Send via WebSocket
      this.ws.send(JSON.stringify(messageData));
      console.log(`✅ Response message sent via WebSocket`);
      return true;
    } catch (error) {
      console.error('❌ Error sending response via WebSocket:', error.message);
      return false;
    }
  }
}

// Start the enhanced bridge
console.log('🤖 Initializing Enhanced QQ-Clawdbot Bridge...');
const bridge = new EnhancedQQClawdbotBridge();

// Keep the process alive
process.on('SIGINT', () => {
  console.log('\n🛑 Shutting down Enhanced QQ-Clawdbot Bridge...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.log('\n🛑 Shutting down Enhanced QQ-Clawdbot Bridge...');
  process.exit(0);
});