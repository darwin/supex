/**
 * Mock WebSocket for testing DriverRelayClient.
 *
 * Replaces the global WebSocket with a controllable mock that records
 * sent messages and allows simulating server responses.
 */

import { vi } from "vitest";

export class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  // Instance mirrors of static constants (matches WebSocket spec)
  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSING = 2;
  readonly CLOSED = 3;

  readyState: number;
  url: string;
  protocol = "";
  extensions = "";
  bufferedAmount = 0;
  binaryType: BinaryType = "blob";

  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  sentMessages: unknown[] = [];

  constructor(url: string | URL, _protocols?: string | string[]) {
    this.url = typeof url === "string" ? url : url.toString();
    this.readyState = MockWebSocket.CONNECTING;
    MockWebSocket._instances.push(this);
  }

  send(data: string): void {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error("WebSocket is not open");
    }
    this.sentMessages.push(JSON.parse(data));
  }

  close(_code?: number, _reason?: string): void {
    if (this.readyState === MockWebSocket.CLOSED) return;
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close"));
  }

  addEventListener(): void {}
  removeEventListener(): void {}
  dispatchEvent(): boolean {
    return false;
  }

  // --- Test helpers ---

  simulateOpen(): void {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  simulateMessage(data: unknown): void {
    const payload = typeof data === "string" ? data : JSON.stringify(data);
    this.onmessage?.(new MessageEvent("message", { data: payload }));
  }

  simulateClose(code = 1000, reason = ""): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close", { code, reason }));
  }

  simulateError(): void {
    this.onerror?.(new Event("error"));
  }

  // --- Static tracking ---

  static _instances: MockWebSocket[] = [];

  static reset(): void {
    MockWebSocket._instances = [];
  }

  static get latest(): MockWebSocket | undefined {
    return MockWebSocket._instances[MockWebSocket._instances.length - 1];
  }

  static install(): void {
    MockWebSocket.reset();
    vi.stubGlobal("WebSocket", MockWebSocket);
  }

  static uninstall(): void {
    MockWebSocket.reset();
    vi.unstubAllGlobals();
  }
}
