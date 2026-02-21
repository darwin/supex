import { useEffect, useRef } from "react";
import { Viewport } from "./Viewport";
import { DriverRelayClient } from "./DriverRelayClient";

export function App() {
  const relayRef = useRef<DriverRelayClient | null>(null);

  useEffect(() => {
    const client = new DriverRelayClient();
    relayRef.current = client;
    client.connect();

    return () => {
      client.dispose();
      relayRef.current = null;
    };
  }, []);

  return (
    <div className="w-full h-full bg-neutral-900">
      <Viewport />
    </div>
  );
}
