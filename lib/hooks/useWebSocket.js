import { useState, useEffect, useRef, useCallback } from 'react';

const useWebSocket = (url) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [error, setError] = useState(null);
  const ws = useRef(null); // Ref to hold the WebSocket instance

  const connect = useCallback(() => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected.');
      return;
    }

    // Clear previous errors/state
    setError(null);
    setIsConnected(false);
    setLastMessage(null);

    console.log(`Attempting to connect WebSocket to ${url}...`);
    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      setError(null);
      // TODO: Send authentication token if required by backend
      // const token = getAuthToken(); // Function to get token
      // if (token) {
      //   ws.current.send(JSON.stringify({ type: 'auth', token: token }));
      // }
    };

    ws.current.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log('WebSocket message received:', message);
        setLastMessage(message); // Store the parsed message
      } catch (e) {
        console.warn('Received non-JSON WebSocket message:', event.data);
        setLastMessage(event.data); // Store raw data if not JSON
      }
    };

    ws.current.onerror = (event) => {
      console.error('WebSocket error:', event);
      setError('WebSocket connection error.'); // Set a generic error message
      setIsConnected(false);
    };

    ws.current.onclose = (event) => {
      console.log(`WebSocket closed: Code=${event.code}, Reason=${event.reason}`);
      setIsConnected(false);
      // Optional: Implement automatic reconnection logic here
      // if (!event.wasClean) {
      //   console.log('Attempting to reconnect WebSocket...');
      //   setTimeout(connect, 5000); // Reconnect after 5 seconds
      // }
    };

  }, [url]); // Re-run connect if URL changes

  const disconnect = useCallback(() => {
    if (ws.current) {
      console.log('Disconnecting WebSocket...');
      ws.current.close();
      ws.current = null;
      setIsConnected(false);
      setLastMessage(null);
    }
  }, []);

  // Effect to connect on mount and disconnect on unmount
  useEffect(() => {
    // Determine WebSocket URL (ws:// or wss://)
    const backendHost = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    // Basic check for http/https to determine ws/wss
    const wsProtocol = backendHost.startsWith('https') ? 'wss://' : 'ws://';
    // Remove http(s):// prefix and append WebSocket path
    const wsUrl = `${wsProtocol}${backendHost.replace(/^https?:\/\//, '')}${url}`; 
    
    connect(wsUrl); // Connect using the derived URL

    // Cleanup function to close connection on unmount
    return () => {
      disconnect();
    };
  }, [url, connect, disconnect]); // Dependencies for the effect

  // Function to send messages (optional)
  const sendMessage = useCallback((message) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(typeof message === 'string' ? message : JSON.stringify(message));
    } else {
      console.error('WebSocket not connected. Cannot send message.');
    }
  }, []);

  return { isConnected, lastMessage, error, sendMessage, connect, disconnect };
};

export default useWebSocket;
