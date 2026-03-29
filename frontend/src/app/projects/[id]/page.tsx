"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { api, createProjectWebSocket, type Project, type Shot } from "@/lib/api";
import { useParams } from "next/navigation";
import Link from "next/link";
import FileUpload from "@/components/FileUpload";
import VoiceSelector from "@/components/VoiceSelector";
import StatusBadge from "@/components/StatusBadge";
import { useToast, ToastContainer } from "@/components/Toast";

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [composing, setComposing] = useState(false);
  const [includeSubtitles, setIncludeSubtitles] = useState(true);
  const [subtitleFontSize, setSubtitleFontSize] = useState(20);
  const [subtitleUrl, setSubtitleUrl] = useState("");
  const [scriptTheme, setScriptTheme] = useState("");
  const [additionalContext, setAdditionalContext] = useState("");
  const [editingShot, setEditingShot] = useState<string | null>(null);
  const [selectedVoice, setSelectedVoice] = useState("BV012_streaming");
  const [showVoicePanel, setShowVoicePanel] = useState(false);
  const [uploadedImages, setUploadedImages] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<"script" | "shots" | "compose">("script");
  const wsRef = useRef<{ close: () => void } | null>(null);
  const { toasts, showToast, removeToast } = useToast();

  const loadProject = useCallback(async () => {
    try {
      const data = await api.getProject(projectId);
      setProject(data);
      if (!scriptTheme && data.theme) setScriptTheme(data.theme);
      // 恢复之前上传的参考图片
      if (data.reference_images && data.reference_images.length > 0 && uploadedImages.length === 0) {
        setUploadedImages(data.reference_images);
      }
      if (data.shots.length > 0 && data.status !== "draft") {
        const hasCompleted = data.shots.some((s: Shot) => s.status === "completed" && s.video_url);
        if (hasCompleted) setActiveTab("compose");
        else setActiveTab("shots");
      }
    } catch (e) {
      console.error("加载项目失败:", e);
      showToast("加载项目失败", "error");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadProject(); }, [loadProject]);

  useEffect(() => {
    if (!project) return;
    const hasGenerating = project.shots.some((s: Shot) => s.status === "generating");
    if (!hasGenerating) return;
    wsRef.current = createProjectWebSocket(projectId, (data) => {
      if (data.type === "shot_update") {
        if (data.status === "completed") showToast(`镜头 ${data.sequence} 完成！`, "success");
        else if (data.status === "failed") showToast(`镜头 ${data.sequence} 失败`, "error");
        loadProject();
      }
      if (data.type === "all_shots_done") { showToast("全部处理完成", "info"); loadProject(); }
    });
    return () => { wsRef.current?.close(); };
  }, [project?.shots.filter((s: Shot) => s.status === "generating").length]);

  useEffect(() => {
    if (!project) return;
    const gen = project.shots.filter((s: Shot) => s.status === "generating");
    if (gen.length === 0) return;
    const interval = setInterval(async () => {
      for (const shot of gen) { try { await api.getVideoStatus(shot.id); } catch {} }
      loadProject();
    }, 15000);
    return () => clearInterval(interval);
  }, [project, loadProject]);

  async function handleGenerateScript() {
    if (!scriptTheme.trim()) return;
    setGenerating(true);
    try {
      await api.generateScript(projectId, {
        theme: scriptTheme, scene_type: project?.scene_type,
        target_duration: project?.target_duration, additional_context: additionalContext,
        image_urls: uploadedImages.length > 0 ? uploadedImages : undefined,
      });
      await loadProject(); setActiveTab("shots"); showToast("脚本生成成功！", "success");
    } catch (e) { showToast("脚本生成失败: " + (e as Error).message, "error"); }
    finally { setGenerating(false); }
  }

  async function handleGenerateAllVideos() {
    setGenerating(true);
    try {
      const r = await api.generateAllVideos(projectId);
      await loadProject(); showToast(r.message || "已提交", "success");
    } catch (e) { showToast("失败: " + (e as Error).message, "error"); }
    finally { setGenerating(false); }
  }

  async function handleGenerateVideo(shotId: string) {
    try {
      await api.generateVideo(shotId, { ratio: project?.aspect_ratio, resolution: project?.resolution });
      await loadProject(); showToast("已提交", "info");
    } catch (e) { showToast("失败: " + (e as Error).message, "error"); }
  }

  async function handleGenerateAudio(shotId: string) {
    try {
      await api.generateShotAudio(shotId, selectedVoice);
      await loadProject(); showToast("语音合成成功", "success");
    } catch (e) { showToast("失败: " + (e as Error).message, "error"); }
  }

  async function handleGenerateAllAudio() {
    if (!project) return;
    const shots = project.shots.filter((s: Shot) => s.dialogue && !s.audio_url);
    for (const shot of shots) { try { await api.generateShotAudio(shot.id, selectedVoice); } catch {} }
    await loadProject(); showToast(`已为 ${shots.length} 个镜头生成语音`, "success");
  }

  async function handleCompose() {
    setComposing(true);
    try {
      const r = await api.composeVideo(projectId, {
        include_audio: true,
        include_subtitles: includeSubtitles,
        subtitle_style: includeSubtitles ? { font_size: subtitleFontSize } : undefined,
      });
      if (r.subtitle_url) setSubtitleUrl(r.subtitle_url);
      await loadProject(); showToast(`合成完成！时长: ${r.duration.toFixed(1)}s`, "success");
    } catch (e) { showToast("失败: " + (e as Error).message, "error"); }
    finally { setComposing(false); }
  }

  async function handleUpdateShot(shotId: string, data: Partial<Shot>) {
    try { await api.updateShot(shotId, data); setEditingShot(null); await loadProject(); }
    catch { showToast("更新失败", "error"); }
  }

  async function handleDeleteShot(shotId: string) {
    if (!confirm("确定删除？")) return;
    try { await api.deleteShot(shotId); await loadProject(); } catch {}
  }

  async function handleAddShot() {
    try { await api.createShot(projectId, { description: "新镜头", dialogue: "", duration: 5 }); await loadProject(); } catch {}
  }

  async function handleImageUpload(file: File) {
    const r = await api.uploadImage(file, projectId);
    setUploadedImages((p) => [...p, r.file_url]); showToast("上传成功", "success");
  }

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" /></div>;
  if (!project) return <div className="min-h-screen flex items-center justify-center"><p className="text-gray-500">项目不存在</p></div>;

  const completedShots = project.shots.filter((s: Shot) => s.status === "completed" && s.video_url);
  const canCompose = completedShots.length > 0;
  const totalDuration = project.shots.reduce((sum: number, s: Shot) => sum + s.duration, 0);

  return (
    <div className="min-h-screen bg-gray-50">
      <ToastContainer toasts={toasts} removeToast={removeToast} />
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/" className="text-gray-400 hover:text-gray-600 text-sm">← 返回</Link>
              <div>
                <h1 className="text-xl font-bold text-gray-900">{project.title}</h1>
                <div className="flex items-center gap-3 mt-1">
                  <StatusBadge status={project.status} />
                  <span className="text-xs text-gray-400">
                    {project.scene_type === "entertainment" ? "🎬 娱乐" : "🔬 科研"} • {project.aspect_ratio} • {project.resolution} • 目标{project.target_duration}s
                  </span>
                </div>
              </div>
            </div>
            <span className="text-sm text-gray-400">{project.shots.length}镜头 • ~{totalDuration}s</span>
          </div>
          <div className="flex gap-1 mt-4 -mb-px">
            {([
              { id: "script" as const, label: "① 脚本", icon: "✍️" },
              { id: "shots" as const, label: `② 分镜(${project.shots.length})`, icon: "🎬" },
              { id: "compose" as const, label: "\u2462 \u5408\u6210", icon: "\uD83C\uDFA5" },
            ]).map((tab) => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors ${activeTab === tab.id ? "bg-white text-blue-600 border border-b-white border-gray-200" : "text-gray-500 hover:text-gray-700"}`}>
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {activeTab === "script" && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl border border-gray-100 p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-2">AI 脚本生成</h2>
              <p className="text-sm text-gray-500 mb-4">输入主题，AI自动生成脚本和分镜。</p>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">视频主题 *</label>
                    <textarea className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" rows={4}
                      placeholder="描述想生成的视频主题..." value={scriptTheme} onChange={(e) => setScriptTheme(e.target.value)} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">补充说明</label>
                    <textarea className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" rows={2}
                      placeholder="额外要求..." value={additionalContext} onChange={(e) => setAdditionalContext(e.target.value)} />
                  </div>
                  <button onClick={handleGenerateScript} disabled={generating || !scriptTheme.trim()}
                    className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium">
                    {generating ? <span className="flex items-center gap-2"><span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />创作中...</span> : "✨ AI 生成脚本"}
                  </button>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">参考图片（强烈推荐！）</label>
                  <p className="text-xs text-gray-400 mb-2">上传主角照片作为第1个镜头的起点，后续镜头自动使用上一镜头尾帧衔接，保证主体一致且场景连续</p>
                  <FileUpload accept="image/jpeg,image/png,image/webp" label="点击或拖拽上传" description="支持多张" onUpload={handleImageUpload} />
                  {uploadedImages.length > 0 && (
                    <div className="mt-3 space-y-2">
                      <div className="flex flex-wrap gap-2">
                        {uploadedImages.map((url, i) => (
                          <div key={i} className="relative w-16 h-16 group">
                            <img src={url} alt="" className="w-full h-full object-cover rounded-lg border border-gray-200" />
                            <button onClick={() => setUploadedImages((p) => p.filter((_, idx) => idx !== i))}
                              className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">✕</button>
                          </div>
                        ))}
                      </div>
                      <p className="text-xs text-blue-500">{uploadedImages.length} 张参考图 → 第1张作为首镜头起点，后续尾帧自动链接</p>
                    </div>
                  )}
                  {project.style_context && (
                    <div className="mt-3 p-2 bg-purple-50 rounded-lg border border-purple-100">
                      <p className="text-xs font-medium text-purple-700 mb-1">🎨 提取的视觉风格</p>
                      <p className="text-xs text-purple-600">{project.style_context}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
            {project.script_json && Object.keys(project.script_json).length > 0 && (
              <div className="bg-white rounded-xl border border-gray-100 p-6">
                <h3 className="font-bold text-gray-900 mb-3">📄 脚本</h3>
                <pre className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 rounded-lg p-4 max-h-96 overflow-auto font-mono">
                  {JSON.stringify(project.script_json, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}

        {activeTab === "shots" && (
          <div className="space-y-4">
            <div className="bg-white rounded-xl border border-gray-100 p-4">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-bold text-gray-900">分镜</h2>
                  <span className="text-sm text-gray-400">{completedShots.length}/{project.shots.length}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={handleAddShot} className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">+ 添加</button>
                  <button onClick={() => setShowVoicePanel(!showVoicePanel)} className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">🎙️ 音色</button>
                  <button onClick={handleGenerateAllAudio} disabled={!project.shots.some((s: Shot) => s.dialogue && !s.audio_url)}
                    className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg disabled:opacity-50">🔊 批量语音</button>
                  <button onClick={handleGenerateAllVideos} disabled={generating}
                    className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded-lg disabled:opacity-50">
                    {generating ? "⏳..." : "🎬 批量生成"}
                  </button>
                </div>
              </div>
              {showVoicePanel && <div className="mt-4 pt-4 border-t border-gray-100"><VoiceSelector value={selectedVoice} onChange={setSelectedVoice} /></div>}
            </div>

            {project.shots.length === 0 ? (
              <div className="bg-white rounded-xl border p-12 text-center text-gray-400">先生成脚本</div>
            ) : (
              project.shots.sort((a: Shot, b: Shot) => a.sequence - b.sequence).map((shot: Shot) => (
                <div key={shot.id} className={`bg-white rounded-xl border transition-all ${editingShot === shot.id ? "border-blue-300 shadow-lg" : "border-gray-100"}`}>
                  <div className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="w-7 h-7 bg-gray-100 rounded-lg text-xs flex items-center justify-center font-bold">{shot.sequence}</span>
                        <StatusBadge status={shot.status} />
                        <span className="text-xs text-gray-400">{shot.duration}s</span>
                      </div>
                      <div className="flex gap-1">
                        <button onClick={() => handleGenerateVideo(shot.id)} disabled={shot.status === "generating"} className="px-2.5 py-1 text-xs bg-blue-50 text-blue-600 rounded-lg disabled:opacity-50 font-medium">🎬</button>
                        {shot.dialogue && <button onClick={() => handleGenerateAudio(shot.id)} className="px-2.5 py-1 text-xs bg-green-50 text-green-600 rounded-lg font-medium">🔊</button>}
                        <button onClick={() => setEditingShot(editingShot === shot.id ? null : shot.id)} className="px-2.5 py-1 text-xs bg-gray-50 rounded-lg">{editingShot === shot.id ? "收起" : "编辑"}</button>
                        <button onClick={() => handleDeleteShot(shot.id)} className="px-2.5 py-1 text-xs text-red-500 rounded-lg hover:bg-red-50">删除</button>
                      </div>
                    </div>

                    {editingShot === shot.id ? (
                      <ShotEditor shot={shot} onSave={(d) => handleUpdateShot(shot.id, d)} onCancel={() => setEditingShot(null)} projectId={projectId} />
                    ) : (
                      <div>
                        <p className="text-sm text-gray-700">{shot.description}</p>
                        {shot.dialogue && <p className="text-sm text-gray-500 italic mt-1">🗣️ &quot;{shot.dialogue}&quot;</p>}
                      </div>
                    )}

                    <div className="flex flex-wrap gap-3 mt-3">
                      {shot.first_frame_url && <div><p className="text-xs text-gray-400 mb-1">首帧</p><img src={shot.first_frame_url} alt="" className="h-20 rounded-lg border" /></div>}
                      {shot.last_frame_url && <div><p className="text-xs text-gray-400 mb-1">尾帧 → 下一镜头</p><img src={shot.last_frame_url} alt="" className="h-20 rounded-lg border border-blue-200" /></div>}
                      {shot.video_url && <div className="flex-1 min-w-[240px]"><p className="text-xs text-gray-400 mb-1">视频</p><video src={shot.video_url} controls className="w-full max-w-sm rounded-lg" /></div>}
                      {shot.audio_url && <div className="flex-1 min-w-[200px]"><p className="text-xs text-gray-400 mb-1">语音({shot.audio_duration.toFixed(1)}s)</p><audio src={shot.audio_url} controls className="w-full" /></div>}
                    </div>
                    {shot.status === "generating" && (
                      <div className="mt-3 flex items-center gap-2 p-2 bg-yellow-50 rounded-lg">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-yellow-600" />
                        <span className="text-sm text-yellow-700">生成中...</span>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === "compose" && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl border border-gray-100 p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4">合成 & 导出</h2>
              <div className="mb-6">
                <div className="flex justify-between text-sm mb-2"><span className="text-gray-500">进度</span><span>{completedShots.length}/{project.shots.length}</span></div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div className="bg-green-500 h-3 rounded-full transition-all" style={{ width: project.shots.length ? `${(completedShots.length / project.shots.length) * 100}%` : "0%" }} />
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                {[
                  { label: "总镜头", value: project.shots.length, color: "text-gray-700" },
                  { label: "已完成", value: completedShots.length, color: "text-green-600" },
                  { label: "生成中", value: project.shots.filter((s: Shot) => s.status === "generating").length, color: "text-yellow-600" },
                  { label: "失败", value: project.shots.filter((s: Shot) => s.status === "failed").length, color: "text-red-600" },
                ].map((item) => (
                  <div key={item.label} className="bg-gray-50 rounded-lg p-3 text-center">
                    <div className={`text-2xl font-bold ${item.color}`}>{item.value}</div>
                    <div className="text-xs text-gray-500">{item.label}</div>
                  </div>
                ))}
              </div>

              {/* 音视频同步说明 */}
              <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-100">
                <p className="text-xs font-medium text-blue-700 mb-1">🔄 音视频同步策略</p>
                <p className="text-xs text-blue-600">每个镜头的音频和视频会精确对齐：音频短于视频则补静音，音频长于视频则冻结末帧延长画面，确保语音和画面完美同步。</p>
              </div>

              {/* 字幕选项 */}
              <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" checked={includeSubtitles} onChange={(e) => setIncludeSubtitles(e.target.checked)} className="sr-only peer" />
                      <div className="w-9 h-5 bg-gray-300 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                    <span className="text-sm font-medium text-gray-700">🔤 烧录字幕</span>
                  </div>
                  <span className="text-xs text-gray-400">根据对白文本自动生成</span>
                </div>
                {includeSubtitles && (
                  <div className="flex items-center gap-4 pt-2 border-t border-gray-200">
                    <div className="flex items-center gap-2">
                      <label className="text-xs text-gray-500">字号</label>
                      <input type="range" min={14} max={40} value={subtitleFontSize} onChange={(e) => setSubtitleFontSize(parseInt(e.target.value))}
                        className="w-24 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600" />
                      <span className="text-xs text-gray-600 w-6">{subtitleFontSize}</span>
                    </div>
                    <p className="text-xs text-gray-400">白色文字 + 黑色描边，底部居中</p>
                  </div>
                )}
              </div>

              {/* 镜头时长明细 */}
              {completedShots.length > 0 && (
                <div className="mb-6">
                  <p className="text-xs font-medium text-gray-500 mb-2">📋 镜头时长明细</p>
                  <div className="flex flex-wrap gap-2">
                    {completedShots.sort((a: Shot, b: Shot) => a.sequence - b.sequence).map((shot: Shot) => (
                      <div key={shot.id} className="flex items-center gap-1 px-2 py-1 bg-gray-100 rounded text-xs">
                        <span className="font-mono text-gray-500">#{shot.sequence}</span>
                        <span className="text-gray-700">🎬{shot.duration}s</span>
                        {shot.audio_url && <span className="text-green-600">🔊{shot.audio_duration.toFixed(1)}s</span>}
                        {shot.dialogue && <span className="text-blue-500" title={shot.dialogue}>💬</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <button onClick={handleCompose} disabled={!canCompose || composing}
                className="px-8 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 font-medium">
                {composing ? <span className="flex items-center gap-2"><span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />合成中...</span> : `🎞️ 合成视频${includeSubtitles ? "（含字幕）" : ""}`}
              </button>
            </div>

            {project.output_video_url && (
              <div className="bg-white rounded-xl border border-green-200 p-6">
                <h3 className="font-bold text-green-800 mb-4">✅ 最终视频</h3>
                <div className="bg-black rounded-xl overflow-hidden max-w-3xl"><video src={project.output_video_url} controls className="w-full" /></div>
                <div className="flex gap-3 mt-4">
                  <a href={project.output_video_url} download className="px-6 py-2 bg-green-600 text-white rounded-lg text-sm font-medium">⬇️ 下载视频</a>
                  {subtitleUrl && (
                    <a href={subtitleUrl} download className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium">📄 下载字幕(SRT)</a>
                  )}
                  <button onClick={() => { navigator.clipboard.writeText(window.location.origin + project.output_video_url); showToast("已复制", "success"); }}
                    className="px-6 py-2 border border-gray-300 rounded-lg text-sm">🔗 复制链接</button>
                </div>
              </div>
            )}

            {completedShots.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-100 p-6">
                <h3 className="font-bold text-gray-900 mb-4">已完成镜头</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {completedShots.sort((a: Shot, b: Shot) => a.sequence - b.sequence).map((shot: Shot) => (
                    <div key={shot.id} className="border border-gray-200 rounded-lg overflow-hidden">
                      <video src={shot.video_url} controls className="w-full aspect-video bg-black" />
                      <div className="p-3">
                        <span className="text-xs bg-gray-100 rounded px-2 py-0.5 font-mono">#{shot.sequence}</span>
                        <span className="text-xs text-gray-400 ml-2">{shot.duration}s</span>
                        <p className="text-xs text-gray-600 line-clamp-2 mt-1">{shot.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

function ShotEditor({ shot, onSave, onCancel, projectId }: { shot: Shot; onSave: (d: Partial<Shot>) => void; onCancel: () => void; projectId: string }) {
  const [desc, setDesc] = useState(shot.description);
  const [dial, setDial] = useState(shot.dialogue);
  const [dur, setDur] = useState(shot.duration);
  return (
    <div className="space-y-3">
      <div><label className="text-xs text-gray-500 font-medium">画面描述</label>
        <textarea className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg mt-1" rows={3} value={desc} onChange={(e) => setDesc(e.target.value)} /></div>
      <div><label className="text-xs text-gray-500 font-medium">对白</label>
        <textarea className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg mt-1" rows={2} value={dial} onChange={(e) => setDial(e.target.value)} /></div>
      <div className="flex items-end gap-3">
        <div><label className="text-xs text-gray-500">时长</label><input type="number" className="w-20 px-2 py-1.5 text-sm border rounded-lg mt-1" value={dur} min={2} max={12} onChange={(e) => setDur(parseInt(e.target.value) || 5)} /></div>
        <div className="flex-1">
          <FileUpload accept="image/jpeg,image/png,image/webp" label="首帧" description="可选" onUpload={async (file) => {
            const r = await api.uploadImage(file, projectId);
            onSave({ first_frame_url: r.file_url } as Partial<Shot>);
          }} previewUrl={shot.first_frame_url || undefined} />
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <button onClick={onCancel} className="px-4 py-1.5 text-sm text-gray-500">取消</button>
        <button onClick={() => onSave({ description: desc, dialogue: dial, duration: dur })} className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded-lg">保存</button>
      </div>
    </div>
  );
}
