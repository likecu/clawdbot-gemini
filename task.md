# Channel Expansion Project Plan

## Phase 1: Infrastructure (Sub-agent: System Architect)
- [x] Create `src/channels/base.py` for `BaseChannel` and `UnifiedMessage` definitions
- [x] Create `src/channels/manager.py` for `ChannelManager`

## Phase 2: Channel Adapters (Sub-agent: Integration Specialist)
- [x] Implement `src/channels/lark/adapter.py` based on `src/adapters/lark/lark_client.py`
- [x] Implement `src/channels/qq/adapter.py` based on `src/adapters/qq/client.py`
    - [x] Filter asterisks from outgoing messages
- [x] Refactor `requirements.txt` if needed (no major dependency changes anticipated)

## Phase 3: Core Integration (Sub-agent: Backend Developer)
- [x] Modify `src/main.py` to use `ChannelManager`
- [x] Ensure `src/core/agent.py` processes `UnifiedMessage` properly (currently agent process raw user requests, might need minor tweaks if signatures change)
- [ ] Add explicit Chinese comments to all new files (Ongoing)

## Phase 4: Local Verification (Sub-agent: QA)
- [ ] Create `tests/test_channels.py` for unit testing the new architecture
- [ ] Run tests and verify basic functionality

## Phase 5: Deployment & Debugging (Sub-agent: DevOps Engineer)
- [x] SSH into remote server
- [x] Pull latest code (Optimized: Force Reset to avoid conflicts)
- [x] Rebuild and restart Docker containers
- [x] Check logs (`docker logs`)
- [x] Verify connectivity by sending a test message
- [x] Fix README.md Mermaid diagram syntax
