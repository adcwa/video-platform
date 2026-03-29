"use client";

import { useEffect, useState } from "react";
import { api, type Project, type Character, type Scene } from "@/lib/api";
import Link from "next/link";
import { useRouter } from "next/navigation";

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft: { label: "草稿", color: "bg-gray-100 text-gray-700" },
  scripting: { label: "脚本生成中", color: "bg-blue-100 text-blue-700" },
  generating: { label: "视频生成中", color: "bg-yellow-100 text-yellow-700" },
  composing: { label: "合成中", color: "bg-purple-100 text-purple-700" },
  completed: { label: "已完成", color: "bg-green-100 text-green-700" },
  failed: { label: "失败", color: "bg-red-100 text-red-700" },
};

export default function HomePage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [createStep, setCreateStep] = useState<1 | 2>(1); // 步骤1: 基本信息, 步骤2: 角色&场景
  const [newProject, setNewProject] = useState({
    title: "",
    theme: "",
    scene_type: "entertainment",
    target_duration: 30,
    aspect_ratio: "16:9",
    resolution: "720p",
  });
  // 创建时选择的角色/场景
  const [selectedCharacterIds, setSelectedCharacterIds] = useState<string[]>([]);
  const [selectedSceneIds, setSelectedSceneIds] = useState<string[]>([]);
  const [allCharacters, setAllCharacters] = useState<Character[]>([]);
  const [allScenes, setAllScenes] = useState<Scene[]>([]);
  const [assetsLoaded, setAssetsLoaded] = useState(false);

  useEffect(() => {
    loadProjects();
  }, []);

  async function loadProjects() {
    try {
      const data = await api.listProjects();
      setProjects(data);
    } catch (e) {
      console.error("加载项目失败:", e);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!newProject.title.trim()) return;
    try {
      const created = await api.createProject(newProject);
      // 关联选中的角色和场景
      for (const charId of selectedCharacterIds) {
        try { await api.addProjectCharacter(created.id, { character_id: charId }); } catch {}
      }
      for (const sceneId of selectedSceneIds) {
        try { await api.addProjectScene(created.id, { scene_id: sceneId }); } catch {}
      }
      setShowCreate(false);
      setCreateStep(1);
      setNewProject({
        title: "",
        theme: "",
        scene_type: "entertainment",
        target_duration: 30,
        aspect_ratio: "16:9",
        resolution: "720p",
      });
      setSelectedCharacterIds([]);
      setSelectedSceneIds([]);
      // 直接跳转到项目详情页
      router.push(`/projects/${created.id}`);
    } catch (e) {
      console.error("创建项目失败:", e);
    }
  }

  async function loadAssets() {
    if (assetsLoaded) return;
    try {
      const [chars, scenes] = await Promise.all([
        api.listCharacters(),
        api.listScenes(),
      ]);
      setAllCharacters(chars);
      setAllScenes(scenes);
      setAssetsLoaded(true);
    } catch {}
  }

  async function handleDelete(id: string) {
    if (!confirm("确定删除此项目？")) return;
    try {
      await api.deleteProject(id);
      loadProjects();
    } catch (e) {
      console.error("删除项目失败:", e);
    }
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </div>
            <h1 className="text-xl font-bold text-gray-900">AI 视频生成平台</h1>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors text-sm font-medium"
          >
            + 创建项目
          </button>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* 数字资产入口 */}
        <Link
          href="/assets"
          className="block mb-6 p-4 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-xl border border-purple-100 hover:border-purple-300 hover:shadow-md transition-all group"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-xl flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 group-hover:text-purple-700 transition-colors">
                  📦 数字资产库
                </h3>
                <p className="text-xs text-gray-500">管理全局角色 & 场景，跨项目复用，AI 图片一键识别</p>
              </div>
            </div>
            <svg className="w-5 h-5 text-gray-400 group-hover:text-purple-600 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </Link>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: "全部项目", value: projects.length, color: "bg-blue-50 text-blue-600" },
            { label: "进行中", value: projects.filter((p) => ["scripting", "generating", "composing"].includes(p.status)).length, color: "bg-yellow-50 text-yellow-600" },
            { label: "已完成", value: projects.filter((p) => p.status === "completed").length, color: "bg-green-50 text-green-600" },
            { label: "失败", value: projects.filter((p) => p.status === "failed").length, color: "bg-red-50 text-red-600" },
          ].map((stat) => (
            <div key={stat.label} className="bg-white rounded-xl p-4 border border-gray-100">
              <div className="text-sm text-gray-500">{stat.label}</div>
              <div className={`text-2xl font-bold mt-1 ${stat.color.split(" ")[1]}`}>{stat.value}</div>
            </div>
          ))}
        </div>

        {/* Loading */}
        {loading && (
          <div className="text-center py-20">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
            <p className="text-gray-500 mt-3">加载中...</p>
          </div>
        )}

        {/* Empty State */}
        {!loading && projects.length === 0 && (
          <div className="text-center py-20 bg-white rounded-2xl border border-gray-100">
            <svg className="w-16 h-16 text-gray-300 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 mt-4">还没有项目</h3>
            <p className="text-gray-500 mt-2">创建你的第一个AI视频项目</p>
            <button
              onClick={() => setShowCreate(true)}
              className="mt-4 px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
            >
              开始创建
            </button>
          </div>
        )}

        {/* Project Grid */}
        {!loading && projects.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((project) => {
              const statusInfo = STATUS_MAP[project.status] || STATUS_MAP.draft;
              return (
                <Link
                  href={`/projects/${project.id}`}
                  key={project.id}
                  className="group bg-white rounded-xl border border-gray-100 hover:border-primary-200 hover:shadow-lg transition-all p-5"
                >
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="font-semibold text-gray-900 group-hover:text-primary-600 transition-colors line-clamp-1">
                      {project.title}
                    </h3>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusInfo.color}`}>
                      {statusInfo.label}
                    </span>
                  </div>
                  {project.description && (
                    <p className="text-sm text-gray-500 line-clamp-2 mb-3">{project.description}</p>
                  )}
                  <div className="flex items-center justify-between text-xs text-gray-400">
                    <span>
                      {project.scene_type === "entertainment" ? "🎬 娱乐发布" : "🔬 科研研究"}
                    </span>
                    <span>{new Date(project.created_at).toLocaleDateString("zh-CN")}</span>
                  </div>
                  <div className="mt-3 flex justify-end">
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        handleDelete(project.id);
                      }}
                      className="text-xs text-red-400 hover:text-red-600 transition-colors"
                    >
                      删除
                    </button>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </main>

      {/* Create Modal — 两步创建 */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">
            {/* 步骤指示器 */}
            <div className="px-6 pt-6 pb-4 border-b border-gray-100">
              <h2 className="text-lg font-bold text-gray-900 mb-3">创建新项目</h2>
              <div className="flex items-center gap-2">
                <button onClick={() => setCreateStep(1)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${createStep === 1 ? "bg-blue-100 text-blue-700" : "text-gray-400 hover:text-gray-600"}`}>
                  <span className="w-5 h-5 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center">1</span>
                  基本信息
                </button>
                <svg className="w-4 h-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                <button onClick={() => { setCreateStep(2); loadAssets(); }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${createStep === 2 ? "bg-purple-100 text-purple-700" : "text-gray-400 hover:text-gray-600"}`}>
                  <span className={`w-5 h-5 rounded-full text-xs flex items-center justify-center ${createStep === 2 ? "bg-purple-600 text-white" : "bg-gray-300 text-white"}`}>2</span>
                  角色 &amp; 场景
                  {(selectedCharacterIds.length + selectedSceneIds.length) > 0 && (
                    <span className="ml-1 px-1.5 py-0.5 bg-purple-200 text-purple-700 rounded text-xs">
                      {selectedCharacterIds.length + selectedSceneIds.length}
                    </span>
                  )}
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-auto px-6 py-4">
              {createStep === 1 && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">项目标题 *</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      placeholder="输入项目标题"
                      value={newProject.title}
                      onChange={(e) => setNewProject({ ...newProject, title: e.target.value })}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">视频主题</label>
                    <textarea
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      rows={3}
                      placeholder="描述你想生成的视频主题..."
                      value={newProject.theme}
                      onChange={(e) => setNewProject({ ...newProject, theme: e.target.value })}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">场景类型</label>
                      <select className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                        value={newProject.scene_type} onChange={(e) => setNewProject({ ...newProject, scene_type: e.target.value })}>
                        <option value="entertainment">🎬 娱乐发布</option>
                        <option value="research">🔬 科研研究</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">目标时长(秒)</label>
                      <input type="number" className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                        min={5} max={300} value={newProject.target_duration}
                        onChange={(e) => setNewProject({ ...newProject, target_duration: parseInt(e.target.value) || 30 })} />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">画面比例</label>
                      <select className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                        value={newProject.aspect_ratio} onChange={(e) => setNewProject({ ...newProject, aspect_ratio: e.target.value })}>
                        <option value="16:9">16:9 横屏</option>
                        <option value="9:16">9:16 竖屏</option>
                        <option value="1:1">1:1 方形</option>
                        <option value="4:3">4:3</option>
                        <option value="3:4">3:4</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">分辨率</label>
                      <select className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                        value={newProject.resolution} onChange={(e) => setNewProject({ ...newProject, resolution: e.target.value })}>
                        <option value="480p">480p</option>
                        <option value="720p">720p</option>
                        <option value="1080p">1080p</option>
                      </select>
                    </div>
                  </div>
                </div>
              )}

              {createStep === 2 && (
                <div className="space-y-6">
                  <div className="p-3 bg-purple-50 rounded-lg border border-purple-100">
                    <p className="text-xs text-purple-700">
                      <strong>💡 重要：</strong>选择角色和场景后，它们的<strong>参考图片</strong>会自动传递给 AI 进行视觉分析，确保生成的视频与角色外观、场景环境高度一致。仅靠文字描述远不如图片精准。
                    </p>
                  </div>

                  {/* 角色选择 */}
                  <div>
                    <h3 className="text-sm font-bold text-gray-900 mb-3">🎭 选择角色 <span className="text-xs text-gray-400 font-normal">（角色参考图将用于 AI 视觉分析）</span></h3>
                    {allCharacters.length === 0 ? (
                      <div className="text-center py-6 text-gray-400 bg-gray-50 rounded-lg">
                        <p className="text-sm">暂无角色</p>
                        <p className="text-xs mt-1">先在 <Link href="/assets" className="text-purple-600 underline">数字资产库</Link> 创建角色</p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {allCharacters.map((ch) => {
                          const selected = selectedCharacterIds.includes(ch.id);
                          return (
                            <button key={ch.id} onClick={() => {
                              setSelectedCharacterIds(prev => selected ? prev.filter(id => id !== ch.id) : [...prev, ch.id]);
                            }}
                              className={`flex items-center gap-3 p-3 rounded-xl border text-left transition-all ${selected ? "border-purple-400 bg-purple-50 ring-1 ring-purple-300" : "border-gray-200 hover:border-purple-200"}`}>
                              {ch.reference_images?.[0] ? (
                                <img src={ch.reference_images[0]} alt="" className="w-11 h-11 rounded-full object-cover border-2 border-white shadow-sm" />
                              ) : (
                                <div className="w-11 h-11 rounded-full bg-purple-100 flex items-center justify-center text-lg">🎭</div>
                              )}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1.5">
                                  <p className="font-medium text-gray-900 text-sm truncate">{ch.name}</p>
                                  {selected && <span className="text-purple-600">✓</span>}
                                </div>
                                <p className="text-xs text-gray-500 truncate">{ch.description || ch.appearance_prompt_zh || "无描述"}</p>
                                <div className="flex items-center gap-2 mt-0.5">
                                  {ch.reference_images.length > 0 && (
                                    <span className="text-xs text-blue-500">📷{ch.reference_images.length}张参考图</span>
                                  )}
                                  {ch.voice_type && <span className="text-xs text-green-500">🎙️</span>}
                                </div>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* 场景选择 */}
                  <div>
                    <h3 className="text-sm font-bold text-gray-900 mb-3">🏞️ 选择场景 <span className="text-xs text-gray-400 font-normal">（场景参考图将用于 AI 视觉分析）</span></h3>
                    {allScenes.length === 0 ? (
                      <div className="text-center py-6 text-gray-400 bg-gray-50 rounded-lg">
                        <p className="text-sm">暂无场景</p>
                        <p className="text-xs mt-1">先在 <Link href="/assets" className="text-purple-600 underline">数字资产库</Link> 创建场景</p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {allScenes.map((sc) => {
                          const selected = selectedSceneIds.includes(sc.id);
                          return (
                            <button key={sc.id} onClick={() => {
                              setSelectedSceneIds(prev => selected ? prev.filter(id => id !== sc.id) : [...prev, sc.id]);
                            }}
                              className={`flex items-center gap-3 p-3 rounded-xl border text-left transition-all ${selected ? "border-blue-400 bg-blue-50 ring-1 ring-blue-300" : "border-gray-200 hover:border-blue-200"}`}>
                              {sc.reference_images?.[0] ? (
                                <img src={sc.reference_images[0]} alt="" className="w-11 h-11 rounded-lg object-cover border-2 border-white shadow-sm" />
                              ) : (
                                <div className="w-11 h-11 rounded-lg bg-blue-100 flex items-center justify-center text-lg">🏞️</div>
                              )}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1.5">
                                  <p className="font-medium text-gray-900 text-sm truncate">{sc.name}</p>
                                  {selected && <span className="text-blue-600">✓</span>}
                                </div>
                                <p className="text-xs text-gray-500 truncate">{sc.description || sc.environment_prompt_zh || "无描述"}</p>
                                <div className="flex items-center gap-2 mt-0.5">
                                  {sc.reference_images.length > 0 && (
                                    <span className="text-xs text-blue-500">📷{sc.reference_images.length}张参考图</span>
                                  )}
                                  {sc.mood && <span className="text-xs text-gray-400">🎭{sc.mood}</span>}
                                </div>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100">
              <button onClick={() => { setShowCreate(false); setCreateStep(1); }}
                className="px-4 py-2 text-gray-600 hover:text-gray-900 transition-colors">
                取消
              </button>
              <div className="flex gap-2">
                {createStep === 2 && (
                  <button onClick={() => setCreateStep(1)}
                    className="px-4 py-2 text-gray-600 hover:text-gray-900 transition-colors text-sm">
                    ← 上一步
                  </button>
                )}
                {createStep === 1 ? (
                  <button onClick={() => { setCreateStep(2); loadAssets(); }}
                    disabled={!newProject.title.trim()}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors text-sm font-medium">
                    下一步：选择角色 & 场景 →
                  </button>
                ) : (
                  <button onClick={handleCreate}
                    disabled={!newProject.title.trim()}
                    className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium">
                    🚀 创建项目 {(selectedCharacterIds.length + selectedSceneIds.length) > 0 ? `(含${selectedCharacterIds.length}角色 ${selectedSceneIds.length}场景)` : ""}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
