"use client";

import { useState, useEffect } from "react";
import { api, type VoiceType } from "@/lib/api";

interface VoiceSelectorProps {
  value: string;
  onChange: (voiceType: string) => void;
  onPreview?: (text: string, voiceType: string) => void;
}

export default function VoiceSelector({ value, onChange, onPreview }: VoiceSelectorProps) {
  const [voices, setVoices] = useState<VoiceType[]>([]);
  const [previewText, setPreviewText] = useState("你好，这是一段语音合成的测试文本。");
  const [previewing, setPreviewing] = useState(false);
  const [audioUrl, setAudioUrl] = useState("");

  useEffect(() => {
    api.getConfig().then((config) => {
      setVoices(config.available_voice_types);
    }).catch(console.error);
  }, []);

  async function handlePreview() {
    if (previewing) return;
    setPreviewing(true);
    try {
      const result = await api.synthesizeSpeech({
        text: previewText,
        voice_type: value,
      });
      setAudioUrl(result.audio_url);
    } catch (e) {
      console.error("预览失败:", e);
    } finally {
      setPreviewing(false);
    }
  }

  const categories = [...new Set(voices.map((v) => v.category))];

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">语音音色</label>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {voices.map((voice) => (
          <button
            key={voice.id}
            type="button"
            onClick={() => onChange(voice.id)}
            className={`
              px-3 py-2 text-left text-sm rounded-lg border transition-all
              ${value === voice.id
                ? "border-blue-500 bg-blue-50 text-blue-700 ring-1 ring-blue-500"
                : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
              }
            `}
          >
            <div className="font-medium">{voice.name}</div>
            <div className="text-xs text-gray-400">{voice.category}</div>
          </button>
        ))}
      </div>

      {/* 预览 */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={previewText}
          onChange={(e) => setPreviewText(e.target.value)}
          className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-lg"
          placeholder="输入预览文本"
        />
        <button
          type="button"
          onClick={handlePreview}
          disabled={previewing || !previewText.trim()}
          className="px-3 py-1.5 text-sm bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 transition-colors"
        >
          {previewing ? "⏳" : "🔊 试听"}
        </button>
      </div>

      {audioUrl && (
        <audio src={audioUrl} controls autoPlay className="w-full" />
      )}
    </div>
  );
}
