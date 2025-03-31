import { useState, useEffect, useRef, useCallback } from 'react';
import { supabase } from '@/lib/supabase'; // Import supabase for auth token

const useWebSocket = (url) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [error, setError] = useState(null);
  const ws = useRef(null); 

  const connect = useCallback(async (wsUrl) => { // Accept wsUrl as argument
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected.');
      return;
    }

    setError(null);
    setIsConnected(false);
    setLastMessage(null);

    // Get auth token *before* attempting connection
    let token = null;
    try {
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();
        if (sessionError) throw new Error(`Supabase auth error: ${sessionError.message}`);
        token = session?.access_token;
        if (!token) {
             console.warn("No auth token found for WebSocket connection.");
             // Decide if connection should proceed without auth or fail
             // For now, let's proceed but log warning. Backend will reject if auth needed.
        }
    } catch (err) {
         console.error("Error getting auth token for WebSocket:", err);
         setError("Failed to get authentication token.");
         return; // Don't attempt connection if token fetch fails critically
    }


    console.log(`Attempting to connect WebSocket to ${wsUrl}...`);
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      setError(null);
      
      // Send authentication token immediately after connection
      if (token) {
        const authMessage = JSON.stringify({ type: 'auth', token: token });
        console.log("Sending WebSocket auth message...");
        ws.current.send(authMessage);
      } else {
         console.warn("Proceeding with WebSocket connection without auth token.");
      }
    };

    ws.current.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        // console.log('WebSocket message received:', message); // Reduce console noise
        setLastMessage(message); 
      } catch (e) {
        console.warn('Received non-JSON WebSocket message:', event.data);
        setLastMessage(event.data); 
      }
    };

    ws.current.onerror = (event) => {
      console.error('WebSocket error:', event);
      setError('WebSocket connection error.'); 
      setIsConnected(false);
    };

    ws.current.onclose = (event) => {
      console.log(`WebSocket closed: Code=${event.code}, Reason=${event.reason}`);
      setIsConnected(false);
      // Optional: Implement automatic reconnection logic here
    };

  }, []); // Removed url from dependencies, pass wsUrl directly

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
    // Determine WebSocket URL 
    const backendHost = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    const wsProtocol = backendHost.startsWith('https') ? 'wss://' : 'ws://';
    const wsUrl = `${wsProtocol}${backendHost.replace(/^https?:\/\//, '')}${url}`; 
    
    connect(wsUrl); // Connect using the derived URL

    return () => {
      disconnect();
    };
    // Pass connect and disconnect to dependency array
  }, [url, connect, disconnect]); 

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
