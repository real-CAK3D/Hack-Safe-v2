// Mock Server for Testing WiFi DensePose UI

export class MockServer {
  constructor() {
    this.endpoints = new Map();
    this.websockets = new Set();
    this.isRunning = false;
    this.setupDefaultEndpoints();
  }

  // Set up default mock endpoints
  setupDefaultEndpoints() {
    // Health endpoints
    this.addEndpoint('GET', '/health/health', () => ({
      status: 'healthy',
      timestamp: new Date().toISOString(),
      components: {
        pose: { status: 'healthy', message: 'Pose detection service running' },
        hardware: { status: 'healthy', message: 'Hardware connected' },
        stream: { status: 'healthy', message: 'Streaming service active' }
      },
      system_metrics: {
        cpu: { percent: Math.random() * 30 + 10 },
        memory: { percent: Math.random() * 40 + 20 },
        disk: { percent: Math.random() * 20 + 5 }
      }
    }));

    this.addEndpoint('GET', '/health/ready', () => ({
      status: 'ready',
      checks: {
        database: 'ready',
        hardware: 'ready',
        inference: 'ready'
      }
    }));

    this.addEndpoint('GET', '/health/live', () => ({
      status: 'alive',
      timestamp: new Date().toISOString()
    }));

    this.addEndpoint('GET', '/health/version', () => ({
      name: 'WiFi-DensePose API',
      version: '1.0.0',
      environment: 'development',
      build: '2025-01-07-dev'
    }));

    // API info endpoints
    this.addEndpoint('GET', '/', () => ({
      name: 'WiFi-DensePose API',
      version: '1.0.0',
      environment: 'development',
      features: {
        pose_estimation: true,
        streaming: true,
        authentication: false,
        rate_limiting: true,
        metrics: true
      },
      endpoints: [
        '/health',
        '/api/v1/pose',
        '/api/v1/stream'
      ]
    }));

    this.addEndpoint('GET', '/api/v1/info', () => ({
      name: 'WiFi-DensePose API',
      version: '1.0.0',
      environment: 'development',
      zones: ['zone1', 'zone2', 'living-room'],
      routers: ['router-001', 'router-002'],
      features: {
        pose_estimation: true,
        streaming: true,
        multi_zone: true,
        real_time: true
      },
      rate_limits: {
        requests_per_minute: 60,
        burst: 10
      }
    }));

    this.addEndpoint('GET', '/api/v1/status', () => ({
      services: {
        api: 'running',
        hardware: 'connected',
        inference: 'ready',
        streaming: Math.random() > 0.5 ? 'active' : 'idle'
      },
      streaming: {
        active_connections: Math.floor(Math.random() * 5),
        total_messages: Math.floor(Math.random() * 1000),
        uptime: Math.floor(Date.now() / 1000) - 1800
      }
    }));

    // Pose endpoints
    this.addEndpoint('GET', '/api/v1/pose/current', () => {
      const personCount = Math.floor(Math.random() * 3);
      return {
        timestamp: new Date().toISOString(),
        persons: this.generateMockPersons(personCount),
        processing_time: Math.random() * 20 + 5,
        zone_id: 'living-room',
        total_detections: Math.floor(Math.random() * 10000)
      };
    });

    this.addEndpoint('GET', '/api/v1/pose/zones/summary', () => ({
      zones: {
        'zone_1': Math.floor(Math.random() * 2),
        'zone_2': Math.floor(Math.random() * 2),
        'zone_3': Math.floor(Math.random() * 2),
        'zone_4': Math.floor(Math.random() * 2)
      }
    }));

    this.addEndpoint('GET', '/api/v1/pose/stats', () => ({
      total_detections: Math.floor(Math.random() * 10000),
      average_confidence: Math.random() * 0.4 + 0.6,
      peak_persons: Math.floor(Math.random() * 5) + 1,
      hours_analyzed: 24
    }));

    // Stream endpoints
    this.addEndpoint('GET', '/api/v1/stream/status', () => ({
      is_active: Math.random() > 0.3,
      connected_clients: Math.floor(Math.random() * 10),
      messages_sent: Math.floor(Math.random() * 5000),
      uptime: Math.floor(Date.now() / 1000) - 900
    }));

    this.addEndpoint('POST', '/api/v1/stream/start', () => ({
      message: 'Streaming started',
      status: 'active'
    }));

    this.addEndpoint('POST', '/api/v1/stream/stop', () => ({
      message: 'Streaming stopped',
      status: 'inactive'
    }));


    // Hack-Safe mirror fallback endpoints: keep the UI fully usable when the
    // real RuView sensing server/camera-supervised training stack is not
    // running. These are explicit mock/demo shapes; live CSI still requires
    // ESP32-S3/C6 hardware and the sensing server.
    this.addEndpoint('GET', '/health/metrics', () => ({
      cpu_usage: Math.random() * 30 + 10,
      memory_usage: Math.random() * 35 + 25,
      disk_usage: Math.random() * 20 + 40,
      timestamp: new Date().toISOString()
    }));

    this.addEndpoint('GET', '/api/v1/metrics', () => ({
      cpu_usage: Math.random() * 30 + 10,
      memory_usage: Math.random() * 35 + 25,
      disk_usage: Math.random() * 20 + 40,
      fps: 12 + Math.random() * 8,
      latency_ms: 25 + Math.random() * 18,
      timestamp: new Date().toISOString()
    }));

    this.addEndpoint('GET', '/api/v1/models', () => ({
      models: [
        { id: 'demo-wifi-densepose-v1', name: 'Demo WiFi DensePose v1', status: 'available', source: 'mock' }
      ],
      active_model: 'demo-wifi-densepose-v1'
    }));

    this.addEndpoint('GET', '/api/v1/models/active', () => ({
      model_id: 'demo-wifi-densepose-v1',
      id: 'demo-wifi-densepose-v1',
      name: 'Demo WiFi DensePose v1',
      loaded: true,
      source: 'mock'
    }));

    this.addEndpoint('GET', '/api/v1/models/demo-wifi-densepose-v1', () => ({
      id: 'demo-wifi-densepose-v1', name: 'Demo WiFi DensePose v1', loaded: true, source: 'mock'
    }));

    this.addEndpoint('POST', '/api/v1/models/load', () => ({ ok: true, status: 'loaded', model_id: 'demo-wifi-densepose-v1' }));
    this.addEndpoint('POST', '/api/v1/models/unload', () => ({ ok: true, status: 'unloaded' }));

    this.addEndpoint('GET', '/api/v1/models/lora/profiles', () => ({ profiles: [] }));
    this.addEndpoint('POST', '/api/v1/models/lora/activate', () => ({ ok: true, status: 'lora-activated' }));

    this.addEndpoint('GET', '/api/v1/recording/list', () => ({ recordings: [] }));
    this.addEndpoint('POST', '/api/v1/recording/start', () => ({ ok: true, recording_id: 'demo-recording', status: 'recording' }));
    this.addEndpoint('POST', '/api/v1/recording/stop', () => ({ ok: true, status: 'stopped' }));
    this.addEndpoint('GET', '/api/v1/train/status', () => ({ active: false, progress: 0, status: 'idle', loss: null, pck: null }));
    this.addEndpoint('POST', '/api/v1/train/start', () => ({ ok: true, active: true, status: 'started' }));
    this.addEndpoint('POST', '/api/v1/train/stop', () => ({ ok: true, active: false, status: 'stopped' }));
    this.addEndpoint('POST', '/api/v1/train/pretrain', () => ({ ok: true, active: true, status: 'pretraining' }));
    this.addEndpoint('POST', '/api/v1/train/lora', () => ({ ok: true, active: true, status: 'lora-training' }));
  }

  // Generate mock person data
  generateMockPersons(count) {
    const persons = [];
    for (let i = 0; i < count; i++) {
      persons.push({
        person_id: `person_${i}`,
        confidence: Math.random() * 0.3 + 0.7,
        bbox: {
          x: Math.random() * 400,
          y: Math.random() * 300,
          width: Math.random() * 100 + 50,
          height: Math.random() * 150 + 100
        },
        keypoints: this.generateMockKeypoints(),
        zone_id: `zone${Math.floor(Math.random() * 3) + 1}`
      });
    }
    return persons;
  }

  // Generate mock keypoints (COCO format)
  generateMockKeypoints() {
    const keypoints = [];
    // Generate keypoints in a rough human pose shape
    const centerX = Math.random() * 600 + 100;
    const centerY = Math.random() * 400 + 100;
    
    // COCO keypoint order: nose, left_eye, right_eye, left_ear, right_ear,
    // left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist, right_wrist,
    // left_hip, right_hip, left_knee, right_knee, left_ankle, right_ankle
    const offsets = [
      [0, -80],     // nose
      [-10, -90],   // left_eye
      [10, -90],    // right_eye
      [-20, -85],   // left_ear
      [20, -85],    // right_ear
      [-40, -40],   // left_shoulder
      [40, -40],    // right_shoulder
      [-60, 10],    // left_elbow
      [60, 10],     // right_elbow
      [-65, 60],    // left_wrist
      [65, 60],     // right_wrist
      [-20, 60],    // left_hip
      [20, 60],     // right_hip
      [-25, 120],   // left_knee
      [25, 120],    // right_knee
      [-25, 180],   // left_ankle
      [25, 180]     // right_ankle
    ];
    
    for (let i = 0; i < 17; i++) {
      keypoints.push({
        x: centerX + offsets[i][0] + (Math.random() - 0.5) * 10,
        y: centerY + offsets[i][1] + (Math.random() - 0.5) * 10,
        confidence: Math.random() * 0.3 + 0.7
      });
    }
    return keypoints;
  }

  // Add a mock endpoint
  addEndpoint(method, path, handler) {
    const key = `${method.toUpperCase()} ${path}`;
    this.endpoints.set(key, handler);
  }

  // Start the mock server
  start() {
    if (this.isRunning) return;
    
    this.isRunning = true;
    this.interceptFetch();
    this.interceptWebSocket();
    console.log('Mock server started');
  }

  // Stop the mock server
  stop() {
    if (!this.isRunning) return;
    
    this.isRunning = false;
    this.restoreFetch();
    this.restoreWebSocket();
    console.log('Mock server stopped');
  }

  // Intercept fetch requests
  interceptFetch() {
    this.originalFetch = window.fetch;
    
    window.fetch = async (url, options = {}) => {
      if (!this.isRunning) {
        return this.originalFetch.call(window, url, options);
      }

      const method = options.method || 'GET';
      const path = new URL(url, window.location.origin).pathname;
      const key = `${method.toUpperCase()} ${path}`;
      
      if (this.endpoints.has(key)) {
        const handler = this.endpoints.get(key);
        const delay = Math.random() * 100 + 50; // Simulate network delay
        
        await new Promise(resolve => setTimeout(resolve, delay));
        
        try {
          const data = handler(options);
          return new Response(JSON.stringify(data), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          });
        } catch (error) {
          return new Response(JSON.stringify({ error: error.message }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' }
          });
        }
      }
      
      // If no mock endpoint, fall back to original fetch
      return this.originalFetch.call(window, url, options);
    };
  }

  // Restore original fetch
  restoreFetch() {
    if (this.originalFetch) {
      window.fetch = this.originalFetch;
    }
  }

  // Intercept WebSocket connections
  interceptWebSocket() {
    this.originalWebSocket = window.WebSocket;
    
    window.WebSocket = class MockWebSocket extends EventTarget {
      constructor(url, protocols) {
        super();
        this.url = url;
        this.protocols = protocols;
        this.readyState = WebSocket.CONNECTING;
        this.bufferedAmount = 0;
        
        // Simulate connection
        setTimeout(() => {
          this.readyState = WebSocket.OPEN;
          const openEvent = new Event('open');
          this.dispatchEvent(openEvent);
          if (typeof this.onopen === 'function') this.onopen(openEvent);
          
          // Start sending mock data
          this.startMockData();
        }, 100);
      }
      
      send(data) {
        if (this.readyState !== WebSocket.OPEN) {
          throw new Error('WebSocket is not open');
        }
        
        // Echo back or handle specific commands
        try {
          const message = JSON.parse(data);
          if (message.type === 'ping') {
            setTimeout(() => {
              const msgEvent = new MessageEvent('message', { data: JSON.stringify({ type: 'pong' }) });
              this.dispatchEvent(msgEvent);
              if (typeof this.onmessage === 'function') this.onmessage(msgEvent);
            }, 10);
          }
        } catch (e) {
          // Not JSON, ignore
        }
      }
      
      close(code = 1000, reason = '') {
        this.readyState = WebSocket.CLOSING;
        setTimeout(() => {
          this.readyState = WebSocket.CLOSED;
          const closeEvent = new CloseEvent('close', { code, reason, wasClean: true });
          this.dispatchEvent(closeEvent);
          if (typeof this.onclose === 'function') this.onclose(closeEvent);
        }, 50);
      }
      
      startMockData() {
        // Send connection established message
        setTimeout(() => {
          const msgEvent = new MessageEvent('message', {
            data: JSON.stringify({
              type: 'connection_established',
              payload: { client_id: 'mock-client-123' }
            })
          });
          this.dispatchEvent(msgEvent);
          if (typeof this.onmessage === 'function') this.onmessage(msgEvent);
        }, 50);
        
        // Send periodic pose data if this is a pose stream
        if (this.url.includes('/stream/pose')) {
          this.poseInterval = setInterval(() => {
            if (this.readyState === WebSocket.OPEN) {
              const personCount = Math.floor(Math.random() * 3);
              const persons = mockServer.generateMockPersons(personCount);
              
              // Match the backend format exactly
              const msgEvent = new MessageEvent('message', {
                data: JSON.stringify({
                  type: 'pose_data',
                  timestamp: new Date().toISOString(),
                  zone_id: 'zone_1',
                  data: {
                    pose: {
                      persons: persons
                    },
                    confidence: Math.random() * 0.3 + 0.7,
                    activity: Math.random() > 0.5 ? 'standing' : 'walking'
                  },
                  metadata: {
                    frame_id: `frame_${Date.now()}`,
                    processing_time_ms: Math.random() * 20 + 5
                  }
                })
              });
              this.dispatchEvent(msgEvent);
              if (typeof this.onmessage === 'function') this.onmessage(msgEvent);
            }
          }, 1000);
        }
        
        // Send periodic sensing frames for the Hack-Safe mirror. This avoids
        // endless reconnect errors when no real RuView sensing server is running.
        if (this.url.includes('/ws/sensing')) {
          this.sensingInterval = setInterval(() => {
            if (this.readyState === WebSocket.OPEN) {
              const t = Date.now() / 1000;
              const variance = 1.5 + Math.sin(t * 0.1);
              const motion = 0.05 + Math.abs(Math.sin(t * 0.3)) * 0.15;
              const msgEvent = new MessageEvent('message', { data: JSON.stringify({
                type: 'sensing_update',
                timestamp: t,
                source: 'simulated',
                _simulated: true,
                nodes: [{ node_id: 1, rssi_dbm: -45 + Math.sin(t * 0.5) * 3, position: [2,0,1.5], amplitude: [], subcarrier_count: 0 }],
                features: { mean_rssi: -45, variance, motion_band_power: motion, breathing_band_power: 0.04, dominant_freq_hz: 0.25, change_points: 0, spectral_power: variance + motion, range: variance * 3, iqr: variance * 1.5 },
                classification: { motion_level: motion > 0.12 ? 'active' : 'present_still', presence: variance > 0.8, confidence: 0.72 },
                signal_field: { grid_size: [20,1,20], values: Array.from({length:400}, (_,i)=>Math.max(0, Math.min(1, 0.15 + 0.25*Math.sin(t+i/20)))) }
              }) });
              this.dispatchEvent(msgEvent);
              if (typeof this.onmessage === 'function') this.onmessage(msgEvent);
            }
          }, 500);
        }

        // Send periodic events if this is an event stream
        if (this.url.includes('/stream/events')) {
          this.eventInterval = setInterval(() => {
            if (this.readyState === WebSocket.OPEN && Math.random() > 0.7) {
              const msgEvent = new MessageEvent('message', {
                data: JSON.stringify({
                  type: 'system_event',
                  payload: {
                    event_type: 'zone_entry',
                    zone_id: 'zone1',
                    person_id: 'person_0',
                    timestamp: new Date().toISOString()
                  }
                })
              });
              this.dispatchEvent(msgEvent);
              if (typeof this.onmessage === 'function') this.onmessage(msgEvent);
            }
          }, 2000);
        }
      }
    };
    
    // Copy static properties
    window.WebSocket.CONNECTING = 0;
    window.WebSocket.OPEN = 1;
    window.WebSocket.CLOSING = 2;
    window.WebSocket.CLOSED = 3;
  }

  // Restore original WebSocket
  restoreWebSocket() {
    if (this.originalWebSocket) {
      window.WebSocket = this.originalWebSocket;
    }
  }

  // Add a custom response
  addCustomResponse(method, path, response) {
    this.addEndpoint(method, path, () => response);
  }

  // Simulate server error
  simulateError(method, path, status = 500, message = 'Internal Server Error') {
    this.addEndpoint(method, path, () => {
      throw new Error(message);
    });
  }

  // Simulate slow response
  addSlowEndpoint(method, path, handler, delay = 2000) {
    this.addEndpoint(method, path, async (...args) => {
      await new Promise(resolve => setTimeout(resolve, delay));
      return handler(...args);
    });
  }
}

// Create and export mock server instance
export const mockServer = new MockServer();