/**
 * 轻量级 event bus，用于跨组件通信（如 stream 期间通知 file tree 轮询）
 */

export type StreamEvent = 'stream-tick' | 'switch-to-dev-tab';

type Listener = () => void;

const listeners: Map<StreamEvent, Set<Listener>> = new Map();

function getListeners(event: StreamEvent): Set<Listener> {
  let set = listeners.get(event);
  if (!set) {
    set = new Set();
    listeners.set(event, set);
  }
  return set;
}

export const eventBus = {
  on(event: StreamEvent, cb: Listener) {
    getListeners(event).add(cb);
  },

  off(event: StreamEvent, cb: Listener) {
    getListeners(event).delete(cb);
  },

  emit(event: StreamEvent) {
    getListeners(event).forEach((cb) => cb());
  },
};
