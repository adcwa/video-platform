// Client-side: talk to backend directly to avoid Next.js proxy timeout
// Server-side (SSR): use relative path through rewrites
const API_BASE =
  typeof window !== "undefined"
    ? process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    : "";

async function fetchAPI(path: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API Error: ${res.status}`);
  }
  return res.json();
}

// ============ Types ============

export interface Project {
  id: string;
  title: string;
  description: string;
  theme: string;
  scene_type: string;
  status: string;
  target_duration: number;
  aspect_ratio: string;
  resolution: string;
  script_content: string;
  script_json: Record<string, unknown>;
  style_context: string;
  reference_images: string[];
  output_video_url: string;
  output_audio_url: string;
  created_at: string;
  updated_at: string;
  shots: Shot[];
}

export interface Shot {
  id: string;
  project_id: string;
  sequence: number;
  description: string;
  dialogue: string;
  duration: number;
  status: string;
  video_task_id: string;
  video_url: string;
  first_frame_url: string;
  last_frame_url: string;
  audio_url: string;
  audio_duration: number;
  camera_fixed: string;
  seed: number;
  created_at: string;
  updated_at: string;
}

export interface VoiceType {
  id: string;
  name: string;
  category: string;
}

export interface PlatformConfig {
  available_voice_types: VoiceType[];
  available_ratios: string[];
  available_resolutions: string[];
  scene_types: { id: string; name: string; description: string }[];
}

export interface UploadResult {
  filename: string;
  file_url: string;
  file_size: number;
  mime_type: string;
}

// ============ API Client ============

export const api = {
  // 项目
  listProjects: (): Promise<Project[]> => fetchAPI("/api/projects"),

  createProject: (data: {
    title: string;
    description?: string;
    theme?: string;
    scene_type?: string;
    target_duration?: number;
    aspect_ratio?: string;
    resolution?: string;
  }): Promise<Project> => fetchAPI("/api/projects", { method: "POST", body: JSON.stringify(data) }),

  getProject: (id: string): Promise<Project> => fetchAPI(`/api/projects/${id}`),

  updateProject: (id: string, data: Partial<Project>): Promise<Project> =>
    fetchAPI(`/api/projects/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  deleteProject: (id: string) =>
    fetchAPI(`/api/projects/${id}`, { method: "DELETE" }),

  // 脚本生成
  generateScript: (
    projectId: string,
    data: {
      theme: string;
      scene_type?: string;
      target_duration?: number;
      additional_context?: string;
      image_urls?: string[];
    }
  ) =>
    fetchAPI(`/api/projects/${projectId}/generate-script`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // 分镜
  listShots: (projectId: string): Promise<Shot[]> => fetchAPI(`/api/projects/${projectId}/shots`),

  createShot: (
    projectId: string,
    data: { description?: string; dialogue?: string; duration?: number }
  ): Promise<Shot> =>
    fetchAPI(`/api/projects/${projectId}/shots`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateShot: (shotId: string, data: Partial<Shot>): Promise<Shot> =>
    fetchAPI(`/api/shots/${shotId}`, { method: "PUT", body: JSON.stringify(data) }),

  deleteShot: (shotId: string) =>
    fetchAPI(`/api/shots/${shotId}`, { method: "DELETE" }),

  // 视频生成
  generateVideo: (
    shotId: string,
    data?: {
      prompt?: string;
      first_frame_url?: string;
      last_frame_url?: string;
      duration?: number;
      ratio?: string;
      resolution?: string;
      generate_audio?: boolean;
    }
  ) =>
    fetchAPI(`/api/shots/${shotId}/generate-video`, {
      method: "POST",
      body: JSON.stringify({ shot_id: shotId, ...data }),
    }),

  getVideoStatus: (shotId: string) =>
    fetchAPI(`/api/shots/${shotId}/video-status`),

  generateAllVideos: (projectId: string) =>
    fetchAPI(`/api/projects/${projectId}/generate-all-videos`, { method: "POST" }),

  // TTS
  synthesizeSpeech: (data: {
    text: string;
    voice_type?: string;
    speed_ratio?: number;
    volume_ratio?: number;
    pitch_ratio?: number;
  }) =>
    fetchAPI("/api/tts/synthesize", { method: "POST", body: JSON.stringify(data) }),

  generateShotAudio: (shotId: string, voiceType?: string) =>
    fetchAPI(
      `/api/shots/${shotId}/generate-audio${voiceType ? `?voice_type=${voiceType}` : ""}`,
      { method: "POST" }
    ),

  // 视频合成
  composeVideo: (projectId: string, includeAudio = true) =>
    fetchAPI(`/api/projects/${projectId}/compose`, {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, include_audio: includeAudio }),
    }),

  // 配置
  getConfig: (): Promise<PlatformConfig> => fetchAPI("/api/config"),

  // 图片分析
  analyzeImage: (imageUrl: string) =>
    fetchAPI(`/api/analyze-image?image_url=${encodeURIComponent(imageUrl)}`, {
      method: "POST",
    }),

  // 文件上传
  uploadImage: async (file: File, projectId?: string): Promise<UploadResult> => {
    const formData = new FormData();
    formData.append("file", file);
    if (projectId) formData.append("project_id", projectId);

    const res = await fetch(`${API_BASE}/api/uploads/image`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(error.detail || `Upload Error: ${res.status}`);
    }
    return res.json();
  },

  uploadVideo: async (file: File, projectId?: string): Promise<UploadResult> => {
    const formData = new FormData();
    formData.append("file", file);
    if (projectId) formData.append("project_id", projectId);

    const res = await fetch(`${API_BASE}/api/uploads/video`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(error.detail || `Upload Error: ${res.status}`);
    }
    return res.json();
  },

  // 获取项目素材
  getProjectAssets: (projectId: string) =>
    fetchAPI(`/api/uploads/assets/${projectId}`),
};

// ============ WebSocket Helper ============

export function createProjectWebSocket(
  projectId: string,
  onMessage: (data: Record<string, unknown>) => void,
  onClose?: () => void,
): { close: () => void } {
  const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsHost = API_BASE
    ? new URL(API_BASE).host
    : window.location.host;
  const wsUrl = `${wsProtocol}//${wsHost}/ws/projects/${projectId}`;

  let ws: WebSocket | null = null;
  let pingInterval: ReturnType<typeof setInterval> | null = null;
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  function connect() {
    if (closed) return;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("[WS] Connected:", projectId);
      // 每30秒发送 ping 保持连接
      pingInterval = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, 30000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "pong") return;
        onMessage(data);
      } catch {
        console.warn("[WS] Invalid message:", event.data);
      }
    };

    ws.onclose = () => {
      console.log("[WS] Disconnected:", projectId);
      if (pingInterval) clearInterval(pingInterval);
      if (!closed) {
        // 自动重连
        reconnectTimeout = setTimeout(connect, 3000);
      }
      onClose?.();
    };

    ws.onerror = (err) => {
      console.error("[WS] Error:", err);
    };
  }

  connect();

  return {
    close: () => {
      closed = true;
      if (pingInterval) clearInterval(pingInterval);
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      ws?.close();
    },
  };
}
