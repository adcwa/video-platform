"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { api, createProjectWebSocket, type Project, type Shot, type Character, type Scene, type ProjectCharacter, type ProjectScene } from "@/lib/api";
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

  // === 角色&场景 状态 ===
  const [projectCharacters, setProjectCharacters] = useState<ProjectCharacter[]>([]);
  const [projectScenes, setProjectScenes] = useState<ProjectScene[]>([]);
  const [allCharacters, setAllCharacters] = useState<Character[]>([]);
  const [allScenes, setAllScenes] = useState<Scene[]>([]);
  const [showCharacterPicker, setShowCharacterPicker] = useState(false);
  const [showScenePicker, setShowScenePicker] = useState(false);
  const [charSearch, setCharSearch] = useState("");
  const [sceneSearch, setSceneSearch] = useState("");

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

  const loadProjectAssets = useCallback(async () => {
    try {
      const [chars, scenes] = await Promise.all([
        api.listProjectCharacters(projectId),
        api.listProjectScenes(projectId),
      ]);
      setProjectCharacters(chars);
      setProjectScenes(scenes);
    } catch (e) {
      console.error("加载项目资产失败:", e);
    }
  }, [projectId]);

  useEffect(() => { loadProject(); loadProjectAssets(); }, [loadProject, loadProjectAssets]);

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

  // === 角色/场景管理 ===
  async function loadGlobalCharacters() {
    try {
      const chars = await api.listCharacters({ search: charSearch || undefined });
      setAllCharacters(chars);
    } catch { /* ignore */ }
  }

  async function loadGlobalScenes() {
    try {
      const scenes = await api.listScenes({ search: sceneSearch || undefined });
      setAllScenes(scenes);
    } catch { /* ignore */ }
  }

  async function handleAddCharacter(characterId: string) {
    try {
      await api.addProjectCharacter(projectId, { character_id: characterId });
      await loadProjectAssets();
      showToast("角色已添加到项目", "success");
    } catch (e) {
      showToast("添加失败: " + (e as Error).message, "error");
    }
  }

  async function handleRemoveCharacter(characterId: string) {
    try {
      await api.removeProjectCharacter(projectId, characterId);
      await loadProjectAssets();
      showToast("已移除角色", "info");
    } catch (e) {
      showToast("移除失败: " + (e as Error).message, "error");
    }
  }

  async function handleAddScene(sceneId: string) {
    try {
      await api.addProjectScene(projectId, { scene_id: sceneId });
      await loadProjectAssets();
      showToast("场景已添加到项目", "success");
    } catch (e) {
      showToast("添加失败: " + (e as Error).message, "error");
    }
  }

  async function handleRemoveScene(sceneId: string) {
    try {
      await api.removeProjectScene(projectId, sceneId);
      await loadProjectAssets();
      showToast("已移除场景", "info");
    } catch (e) {
      showToast("移除失败: " + (e as Error).message, "error");
    }
  }

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
              { id: "script" as const, label: `① 设定 & 脚本${projectCharacters.length + projectScenes.length > 0 ? ` (${projectCharacters.length}角色 ${projectScenes.length}场景)` : ""}`, icon: "✍️" },
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
                  {/* 已关联的角色/场景提示 */}
                  {(projectCharacters.length > 0 || projectScenes.length > 0) && (
                    <div className="p-3 bg-purple-50 rounded-lg border border-purple-100">
                      <p className="text-xs font-medium text-purple-700 mb-1">🎭 已关联资产（参考图片 + 文字描述均会自动注入 AI 生成）</p>
                      <div className="flex flex-wrap gap-2">
                        {projectCharacters.map((pc) => (
                          <span key={pc.id} className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">
                            {pc.character.reference_images?.[0] && <img src={pc.character.reference_images[0]} alt="" className="w-4 h-4 rounded-full object-cover" />}
                            🎭 {pc.character.name}
                            {pc.character.reference_images.length > 0 && <span className="text-purple-400">📷{pc.character.reference_images.length}</span>}
                          </span>
                        ))}
                        {projectScenes.map((ps) => (
                          <span key={ps.id} className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                            {ps.scene.reference_images?.[0] && <img src={ps.scene.reference_images[0]} alt="" className="w-4 h-4 rounded object-cover" />}
                            🏞️ {ps.scene.name}
                            {ps.scene.reference_images.length > 0 && <span className="text-blue-400">📷{ps.scene.reference_images.length}</span>}
                          </span>
                        ))}
                      </div>
                      <p className="text-xs text-purple-500 mt-1">在下方「角色 & 场景」区域管理 ↓</p>
                    </div>
                  )}
                  {projectCharacters.length === 0 && projectScenes.length === 0 && (
                    <p className="text-xs text-gray-400">
                      💡 在下方添加角色和场景，它们的参考图片会自动传递给 AI 进行视觉分析 ↓
                    </p>
                  )}
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

            {/* === 角色 & 场景管理（内嵌在脚本标签页） === */}
            <div className="bg-white rounded-xl border border-gray-100 p-6">
              <div className="flex items-center justify-between mb-1">
                <h2 className="text-lg font-bold text-gray-900">🎭 角色 & 场景</h2>
                <div className="flex gap-2">
                  <button onClick={() => { setShowCharacterPicker(true); loadGlobalCharacters(); }}
                    className="px-3 py-1.5 text-xs bg-purple-600 text-white rounded-lg hover:bg-purple-700">+ 角色</button>
                  <button onClick={() => { setShowScenePicker(true); loadGlobalScenes(); }}
                    className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700">+ 场景</button>
                </div>
              </div>
              <p className="text-xs text-gray-400 mb-4">参考图片会直接传递给 AI 视觉分析，远比纯文字准确。在此配置角色和场景后再生成脚本效果最佳。</p>

              {projectCharacters.length === 0 && projectScenes.length === 0 ? (
                <div className="text-center py-6 text-gray-400 bg-gray-50 rounded-lg">
                  <p className="text-2xl mb-1">🎭🏞️</p>
                  <p className="text-sm">尚未添加角色或场景</p>
                  <p className="text-xs mt-1">从 <Link href="/assets" className="text-purple-600 underline">数字资产库</Link> 添加，或点击上方按钮选择</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* 角色列表 */}
                  {projectCharacters.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-2">角色 ({projectCharacters.length})</p>
                      <div className="flex flex-wrap gap-2">
                        {projectCharacters.map((pc) => (
                          <div key={pc.id} className="flex items-center gap-2 px-3 py-2 bg-purple-50 border border-purple-100 rounded-xl group">
                            {pc.character.reference_images?.[0] ? (
                              <img src={pc.character.reference_images[0]} alt="" className="w-8 h-8 rounded-full object-cover border border-purple-200" />
                            ) : (
                              <div className="w-8 h-8 rounded-full bg-purple-200 flex items-center justify-center text-sm">🎭</div>
                            )}
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-gray-900 truncate">{pc.character.name}</p>
                              <div className="flex items-center gap-1.5 text-xs text-gray-400">
                                {pc.character.reference_images.length > 0 && <span className="text-blue-500">📷{pc.character.reference_images.length}</span>}
                                {(pc.custom_voice_type || pc.character.voice_type) && <span className="text-green-500">🎙️</span>}
                                {(pc.custom_appearance_prompt || pc.character.appearance_prompt) && <span>✏️</span>}
                              </div>
                            </div>
                            <button onClick={() => handleRemoveCharacter(pc.character_id)}
                              className="text-gray-300 hover:text-red-500 text-xs opacity-0 group-hover:opacity-100 transition-opacity ml-1">✕</button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* 场景列表 */}
                  {projectScenes.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-2">场景 ({projectScenes.length})</p>
                      <div className="flex flex-wrap gap-2">
                        {projectScenes.map((ps) => (
                          <div key={ps.id} className="flex items-center gap-2 px-3 py-2 bg-blue-50 border border-blue-100 rounded-xl group">
                            {ps.scene.reference_images?.[0] ? (
                              <img src={ps.scene.reference_images[0]} alt="" className="w-8 h-8 rounded-lg object-cover border border-blue-200" />
                            ) : (
                              <div className="w-8 h-8 rounded-lg bg-blue-200 flex items-center justify-center text-sm">🏞️</div>
                            )}
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-gray-900 truncate">{ps.scene.name}</p>
                              <div className="flex items-center gap-1.5 text-xs text-gray-400">
                                {ps.scene.reference_images.length > 0 && <span className="text-blue-500">📷{ps.scene.reference_images.length}</span>}
                                {ps.scene.mood && <span>🎭{ps.scene.mood}</span>}
                              </div>
                            </div>
                            <button onClick={() => handleRemoveScene(ps.scene_id)}
                              className="text-gray-300 hover:text-red-500 text-xs opacity-0 group-hover:opacity-100 transition-opacity ml-1">✕</button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
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

        {/* === 角色选择弹窗 === */}
        {showCharacterPicker && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowCharacterPicker(false)}>
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
              <div className="p-6 border-b border-gray-200">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-gray-900">选择角色</h3>
                  <button onClick={() => setShowCharacterPicker(false)} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
                </div>
                <div className="flex gap-2">
                  <input type="text" placeholder="搜索角色..." className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    value={charSearch} onChange={(e) => setCharSearch(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") loadGlobalCharacters(); }} />
                  <button onClick={loadGlobalCharacters} className="px-4 py-2 bg-gray-100 rounded-lg text-sm hover:bg-gray-200">搜索</button>
                </div>
              </div>
              <div className="flex-1 overflow-auto p-6">
                {allCharacters.length === 0 ? (
                  <div className="text-center py-12 text-gray-400">
                    <p className="text-sm">没有可用角色</p>
                    <p className="text-xs mt-1">请先在 <Link href="/assets" className="text-purple-600 underline">数字资产库</Link> 创建角色</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {allCharacters.map((ch) => {
                      const alreadyAdded = projectCharacters.some((pc) => pc.character_id === ch.id);
                      return (
                        <div key={ch.id} className={`border rounded-xl p-3 flex items-center gap-3 transition-colors ${alreadyAdded ? "border-green-200 bg-green-50" : "border-gray-200 hover:border-purple-200"}`}>
                          {ch.reference_images?.[0] ? (
                            <img src={ch.reference_images[0]} alt="" className="w-10 h-10 rounded-full object-cover border" />
                          ) : (
                            <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center text-lg">🎭</div>
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-gray-900 text-sm truncate">{ch.name}</p>
                            <p className="text-xs text-gray-500 truncate">{ch.description || ch.appearance_prompt || "无描述"}</p>
                            <div className="flex items-center gap-2">
                              {ch.reference_images.length > 0 && <span className="text-xs text-blue-500">📷{ch.reference_images.length}张参考图</span>}
                              {ch.voice_type && <p className="text-xs text-green-600">🎙️ {ch.voice_type}</p>}
                            </div>
                          </div>
                          {alreadyAdded ? (
                            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-lg text-xs font-medium">已添加</span>
                          ) : (
                            <button onClick={() => handleAddCharacter(ch.id)}
                              className="px-3 py-1 bg-purple-600 text-white rounded-lg text-xs font-medium hover:bg-purple-700">添加</button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* === 场景选择弹窗 === */}
        {showScenePicker && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowScenePicker(false)}>
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
              <div className="p-6 border-b border-gray-200">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-gray-900">选择场景</h3>
                  <button onClick={() => setShowScenePicker(false)} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
                </div>
                <div className="flex gap-2">
                  <input type="text" placeholder="搜索场景..." className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    value={sceneSearch} onChange={(e) => setSceneSearch(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") loadGlobalScenes(); }} />
                  <button onClick={loadGlobalScenes} className="px-4 py-2 bg-gray-100 rounded-lg text-sm hover:bg-gray-200">搜索</button>
                </div>
              </div>
              <div className="flex-1 overflow-auto p-6">
                {allScenes.length === 0 ? (
                  <div className="text-center py-12 text-gray-400">
                    <p className="text-sm">没有可用场景</p>
                    <p className="text-xs mt-1">请先在 <Link href="/assets" className="text-purple-600 underline">数字资产库</Link> 创建场景</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {allScenes.map((sc) => {
                      const alreadyAdded = projectScenes.some((ps) => ps.scene_id === sc.id);
                      return (
                        <div key={sc.id} className={`border rounded-xl p-3 flex items-center gap-3 transition-colors ${alreadyAdded ? "border-green-200 bg-green-50" : "border-gray-200 hover:border-blue-200"}`}>
                          {sc.reference_images?.[0] ? (
                            <img src={sc.reference_images[0]} alt="" className="w-10 h-10 rounded-lg object-cover border" />
                          ) : (
                            <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center text-lg">🏞️</div>
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-gray-900 text-sm truncate">{sc.name}</p>
                            <p className="text-xs text-gray-500 truncate">{sc.description || sc.environment_prompt || "无描述"}</p>
                            <div className="flex gap-2 text-xs text-gray-400">
                              {sc.reference_images.length > 0 && <span className="text-blue-500">📷{sc.reference_images.length}张参考图</span>}
                              {sc.mood && <span>🎭{sc.mood}</span>}
                              {sc.lighting && <span>💡{sc.lighting}</span>}
                            </div>
                          </div>
                          {alreadyAdded ? (
                            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-lg text-xs font-medium">已添加</span>
                          ) : (
                            <button onClick={() => handleAddScene(sc.id)}
                              className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700">添加</button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
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
