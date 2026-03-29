"use client";

import { useEffect, useState, useCallback } from "react";
import {
  api,
  type Character,
  type Scene,
  type AssetStats,
  type RecognitionResult,
} from "@/lib/api";
import Link from "next/link";
import FileUpload from "@/components/FileUpload";
import { useToast, ToastContainer } from "@/components/Toast";

type TabType = "characters" | "scenes" | "recognize";

export default function AssetsPage() {
  const [activeTab, setActiveTab] = useState<TabType>("characters");
  const [characters, setCharacters] = useState<Character[]>([]);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [stats, setStats] = useState<AssetStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const { toasts, showToast, removeToast } = useToast();

  // 角色编辑
  const [showCharForm, setShowCharForm] = useState(false);
  const [editingChar, setEditingChar] = useState<Character | null>(null);
  const [charForm, setCharForm] = useState({
    name: "",
    description: "",
    appearance_prompt: "",
    appearance_prompt_zh: "",
    voice_type: "",
    tags: "",
    reference_images: [] as string[],
  });

  // 场景编辑
  const [showSceneForm, setShowSceneForm] = useState(false);
  const [editingScene, setEditingScene] = useState<Scene | null>(null);
  const [sceneForm, setSceneForm] = useState({
    name: "",
    description: "",
    environment_prompt: "",
    environment_prompt_zh: "",
    mood: "",
    lighting: "",
    tags: "",
    reference_images: [] as string[],
  });

  // 图片识别
  const [recognizing, setRecognizing] = useState(false);
  const [recognitionResult, setRecognitionResult] = useState<RecognitionResult | null>(null);
  const [recognizeImageUrl, setRecognizeImageUrl] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [chars, scns, st] = await Promise.all([
        api.listCharacters({ search: searchQuery || undefined }),
        api.listScenes({ search: searchQuery || undefined }),
        api.getAssetStats(),
      ]);
      setCharacters(chars);
      setScenes(scns);
      setStats(st);
    } catch (e) {
      showToast("加载失败: " + (e as Error).message, "error");
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // === 角色操作 ===
  function openCharForm(char?: Character) {
    if (char) {
      setEditingChar(char);
      setCharForm({
        name: char.name,
        description: char.description,
        appearance_prompt: char.appearance_prompt,
        appearance_prompt_zh: char.appearance_prompt_zh,
        voice_type: char.voice_type,
        tags: char.tags.join(", "),
        reference_images: char.reference_images,
      });
    } else {
      setEditingChar(null);
      setCharForm({
        name: "",
        description: "",
        appearance_prompt: "",
        appearance_prompt_zh: "",
        voice_type: "",
        tags: "",
        reference_images: [],
      });
    }
    setShowCharForm(true);
  }

  async function handleSaveChar() {
    if (!charForm.name.trim()) return;
    try {
      const data = {
        name: charForm.name,
        description: charForm.description,
        appearance_prompt: charForm.appearance_prompt,
        appearance_prompt_zh: charForm.appearance_prompt_zh,
        voice_type: charForm.voice_type,
        tags: charForm.tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        reference_images: charForm.reference_images,
        is_global: true,
      };
      if (editingChar) {
        await api.updateCharacter(editingChar.id, data);
        showToast("角色更新成功", "success");
      } else {
        await api.createCharacter(data);
        showToast("角色创建成功", "success");
      }
      setShowCharForm(false);
      loadData();
    } catch (e) {
      showToast("保存失败: " + (e as Error).message, "error");
    }
  }

  async function handleDeleteChar(id: string, name: string) {
    if (!confirm(`确定删除角色 "${name}"？`)) return;
    try {
      await api.deleteCharacter(id);
      showToast("角色已删除", "success");
      loadData();
    } catch (e) {
      showToast("删除失败: " + (e as Error).message, "error");
    }
  }

  // === 场景操作 ===
  function openSceneForm(scene?: Scene) {
    if (scene) {
      setEditingScene(scene);
      setSceneForm({
        name: scene.name,
        description: scene.description,
        environment_prompt: scene.environment_prompt,
        environment_prompt_zh: scene.environment_prompt_zh,
        mood: scene.mood,
        lighting: scene.lighting,
        tags: scene.tags.join(", "),
        reference_images: scene.reference_images,
      });
    } else {
      setEditingScene(null);
      setSceneForm({
        name: "",
        description: "",
        environment_prompt: "",
        environment_prompt_zh: "",
        mood: "",
        lighting: "",
        tags: "",
        reference_images: [],
      });
    }
    setShowSceneForm(true);
  }

  async function handleSaveScene() {
    if (!sceneForm.name.trim()) return;
    try {
      const data = {
        name: sceneForm.name,
        description: sceneForm.description,
        environment_prompt: sceneForm.environment_prompt,
        environment_prompt_zh: sceneForm.environment_prompt_zh,
        mood: sceneForm.mood,
        lighting: sceneForm.lighting,
        tags: sceneForm.tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        reference_images: sceneForm.reference_images,
        is_global: true,
      };
      if (editingScene) {
        await api.updateScene(editingScene.id, data);
        showToast("场景更新成功", "success");
      } else {
        await api.createScene(data);
        showToast("场景创建成功", "success");
      }
      setShowSceneForm(false);
      loadData();
    } catch (e) {
      showToast("保存失败: " + (e as Error).message, "error");
    }
  }

  async function handleDeleteScene(id: string, name: string) {
    if (!confirm(`确定删除场景 "${name}"？`)) return;
    try {
      await api.deleteScene(id);
      showToast("场景已删除", "success");
      loadData();
    } catch (e) {
      showToast("删除失败: " + (e as Error).message, "error");
    }
  }

  // === AI 识别 ===
  async function handleRecognize() {
    if (!recognizeImageUrl.trim()) return;
    setRecognizing(true);
    setRecognitionResult(null);
    try {
      const result = await api.recognizeImage(recognizeImageUrl, true);
      setRecognitionResult(result);
      showToast(
        `识别完成！${result.created_characters.length} 个角色, ${result.created_scenes.length} 个场景`,
        "success"
      );
      loadData();
    } catch (e) {
      showToast("识别失败: " + (e as Error).message, "error");
    } finally {
      setRecognizing(false);
    }
  }

  async function handleImageUploadForRecognize(file: File) {
    try {
      const r = await api.uploadImage(file);
      setRecognizeImageUrl(r.file_url);
      showToast("上传成功，点击「AI 识别」开始分析", "success");
    } catch (e) {
      showToast("上传失败: " + (e as Error).message, "error");
    }
  }

  async function handleCharImageUpload(file: File) {
    try {
      const r = await api.uploadImage(file);
      setCharForm((f) => ({ ...f, reference_images: [...f.reference_images, r.file_url] }));
    } catch (e) {
      showToast("上传失败", "error");
    }
  }

  async function handleSceneImageUpload(file: File) {
    try {
      const r = await api.uploadImage(file);
      setSceneForm((f) => ({ ...f, reference_images: [...f.reference_images, r.file_url] }));
    } catch (e) {
      showToast("上传失败", "error");
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <ToastContainer toasts={toasts} removeToast={removeToast} />

      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/" className="text-gray-400 hover:text-gray-600 text-sm">
                ← 返回首页
              </Link>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-xl flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                </div>
                <div>
                  <h1 className="text-xl font-bold text-gray-900">数字资产库</h1>
                  <p className="text-xs text-gray-400">全局角色 & 场景管理，跨项目复用</p>
                </div>
              </div>
            </div>
            {stats && (
              <div className="flex gap-4 text-sm">
                <span className="text-purple-600 font-medium">
                  🎭 {stats.characters.total} 角色
                </span>
                <span className="text-blue-600 font-medium">
                  🏞️ {stats.scenes.total} 场景
                </span>
              </div>
            )}
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mt-4 -mb-px">
            {(
              [
                { id: "characters" as const, label: "🎭 角色管理", count: characters.length },
                { id: "scenes" as const, label: "🏞️ 场景管理", count: scenes.length },
                { id: "recognize" as const, label: "🔍 AI 图片识别" },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors ${
                  activeTab === tab.id
                    ? "bg-white text-purple-600 border border-b-white border-gray-200"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {tab.label}
                {"count" in tab && tab.count !== undefined && (
                  <span className="ml-1.5 text-xs bg-gray-100 rounded-full px-1.5 py-0.5">
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* Search Bar */}
        {activeTab !== "recognize" && (
          <div className="mb-6">
            <input
              type="text"
              placeholder="搜索角色/场景名称..."
              className="w-full max-w-md px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        )}

        {loading && (
          <div className="text-center py-20">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600 mx-auto" />
            <p className="text-gray-500 mt-3">加载中...</p>
          </div>
        )}

        {/* ============ 角色管理 ============ */}
        {!loading && activeTab === "characters" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">全局角色</h2>
              <button
                onClick={() => openCharForm()}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium"
              >
                + 新建角色
              </button>
            </div>

            {characters.length === 0 ? (
              <div className="bg-white rounded-xl border p-12 text-center">
                <div className="text-5xl mb-4">🎭</div>
                <h3 className="text-lg font-medium text-gray-900">还没有角色</h3>
                <p className="text-gray-500 mt-2">创建你的第一个数字角色，或通过 AI 图片识别自动创建</p>
                <div className="flex gap-3 justify-center mt-4">
                  <button
                    onClick={() => openCharForm()}
                    className="px-6 py-2 bg-purple-600 text-white rounded-lg text-sm"
                  >
                    手动创建
                  </button>
                  <button
                    onClick={() => setActiveTab("recognize")}
                    className="px-6 py-2 border border-purple-300 text-purple-600 rounded-lg text-sm"
                  >
                    🔍 AI 识别创建
                  </button>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {characters.map((char) => (
                  <div
                    key={char.id}
                    className="bg-white rounded-xl border border-gray-100 hover:border-purple-200 hover:shadow-md transition-all p-5"
                  >
                    <div className="flex items-start gap-3">
                      {char.reference_images.length > 0 ? (
                        <img
                          src={char.reference_images[0]}
                          alt={char.name}
                          className="w-16 h-16 rounded-lg object-cover border border-gray-200 flex-shrink-0"
                        />
                      ) : (
                        <div className="w-16 h-16 rounded-lg bg-purple-50 flex items-center justify-center flex-shrink-0">
                          <span className="text-2xl">🎭</span>
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-gray-900 truncate">{char.name}</h3>
                          {char.is_global && (
                            <span className="px-1.5 py-0.5 bg-purple-100 text-purple-700 text-xs rounded-full font-medium">
                              全局
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 mt-1 line-clamp-2">{char.description}</p>
                      </div>
                    </div>

                    {char.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-3">
                        {char.tags.map((tag) => (
                          <span key={tag} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}

                    {char.appearance_prompt && (
                      <div className="mt-3 p-2 bg-gray-50 rounded-lg">
                        <p className="text-xs text-gray-400 font-medium mb-1">🎨 Appearance Prompt</p>
                        <p className="text-xs text-gray-600 line-clamp-2">{char.appearance_prompt}</p>
                      </div>
                    )}

                    {char.voice_type && (
                      <p className="text-xs text-green-600 mt-2">🎙️ 语音: {char.voice_type}</p>
                    )}

                    <div className="flex justify-between items-center mt-3 pt-3 border-t border-gray-50">
                      <span className="text-xs text-gray-400">
                        {new Date(char.updated_at).toLocaleDateString("zh-CN")}
                      </span>
                      <div className="flex gap-2">
                        {!char.is_global && (
                          <button
                            onClick={async () => {
                              await api.promoteCharacter(char.id);
                              showToast("已升级为全局角色", "success");
                              loadData();
                            }}
                            className="text-xs text-purple-600 hover:text-purple-800"
                          >
                            ⬆️ 升级全局
                          </button>
                        )}
                        <button
                          onClick={() => openCharForm(char)}
                          className="text-xs text-blue-600 hover:text-blue-800"
                        >
                          编辑
                        </button>
                        <button
                          onClick={() => handleDeleteChar(char.id, char.name)}
                          className="text-xs text-red-500 hover:text-red-700"
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ============ 场景管理 ============ */}
        {!loading && activeTab === "scenes" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">全局场景</h2>
              <button
                onClick={() => openSceneForm()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
              >
                + 新建场景
              </button>
            </div>

            {scenes.length === 0 ? (
              <div className="bg-white rounded-xl border p-12 text-center">
                <div className="text-5xl mb-4">🏞️</div>
                <h3 className="text-lg font-medium text-gray-900">还没有场景</h3>
                <p className="text-gray-500 mt-2">创建你的第一个数字场景，或通过 AI 图片识别自动创建</p>
                <div className="flex gap-3 justify-center mt-4">
                  <button
                    onClick={() => openSceneForm()}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm"
                  >
                    手动创建
                  </button>
                  <button
                    onClick={() => setActiveTab("recognize")}
                    className="px-6 py-2 border border-blue-300 text-blue-600 rounded-lg text-sm"
                  >
                    🔍 AI 识别创建
                  </button>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {scenes.map((scene) => (
                  <div
                    key={scene.id}
                    className="bg-white rounded-xl border border-gray-100 hover:border-blue-200 hover:shadow-md transition-all p-5"
                  >
                    <div className="flex items-start gap-3">
                      {scene.reference_images.length > 0 ? (
                        <img
                          src={scene.reference_images[0]}
                          alt={scene.name}
                          className="w-16 h-16 rounded-lg object-cover border border-gray-200 flex-shrink-0"
                        />
                      ) : (
                        <div className="w-16 h-16 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
                          <span className="text-2xl">🏞️</span>
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-gray-900 truncate">{scene.name}</h3>
                          {scene.is_global && (
                            <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full font-medium">
                              全局
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 mt-1 line-clamp-2">{scene.description}</p>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2 mt-3">
                      {scene.mood && (
                        <span className="px-2 py-0.5 bg-yellow-50 text-yellow-700 text-xs rounded-full">
                          🎭 {scene.mood}
                        </span>
                      )}
                      {scene.lighting && (
                        <span className="px-2 py-0.5 bg-amber-50 text-amber-700 text-xs rounded-full">
                          💡 {scene.lighting}
                        </span>
                      )}
                      {scene.tags.map((tag) => (
                        <span key={tag} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
                          {tag}
                        </span>
                      ))}
                    </div>

                    {scene.environment_prompt && (
                      <div className="mt-3 p-2 bg-gray-50 rounded-lg">
                        <p className="text-xs text-gray-400 font-medium mb-1">🌍 Environment Prompt</p>
                        <p className="text-xs text-gray-600 line-clamp-2">{scene.environment_prompt}</p>
                      </div>
                    )}

                    <div className="flex justify-between items-center mt-3 pt-3 border-t border-gray-50">
                      <span className="text-xs text-gray-400">
                        {new Date(scene.updated_at).toLocaleDateString("zh-CN")}
                      </span>
                      <div className="flex gap-2">
                        {!scene.is_global && (
                          <button
                            onClick={async () => {
                              await api.promoteScene(scene.id);
                              showToast("已升级为全局场景", "success");
                              loadData();
                            }}
                            className="text-xs text-blue-600 hover:text-blue-800"
                          >
                            ⬆️ 升级全局
                          </button>
                        )}
                        <button
                          onClick={() => openSceneForm(scene)}
                          className="text-xs text-blue-600 hover:text-blue-800"
                        >
                          编辑
                        </button>
                        <button
                          onClick={() => handleDeleteScene(scene.id, scene.name)}
                          className="text-xs text-red-500 hover:text-red-700"
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ============ AI 图片识别 ============ */}
        {!loading && activeTab === "recognize" && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl border border-gray-100 p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-2">🔍 AI 图片智能识别</h2>
              <p className="text-sm text-gray-500 mb-6">
                上传图片，AI 自动识别其中的角色和场景，一键创建为全局数字资产
              </p>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div>
                  <FileUpload
                    accept="image/jpeg,image/png,image/webp"
                    label="点击或拖拽上传图片"
                    description="支持 JPG、PNG、WebP"
                    onUpload={handleImageUploadForRecognize}
                  />
                  {recognizeImageUrl && (
                    <div className="mt-4">
                      <img
                        src={recognizeImageUrl}
                        alt="待识别"
                        className="w-full max-h-64 object-contain rounded-lg border border-gray-200"
                      />
                    </div>
                  )}
                  <button
                    onClick={handleRecognize}
                    disabled={!recognizeImageUrl || recognizing}
                    className="mt-4 w-full px-6 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 font-medium"
                  >
                    {recognizing ? (
                      <span className="flex items-center justify-center gap-2">
                        <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                        AI 识别中...
                      </span>
                    ) : (
                      "🤖 AI 识别并创建资产"
                    )}
                  </button>
                </div>

                {recognitionResult && (
                  <div className="space-y-4">
                    <h3 className="font-bold text-gray-900">识别结果</h3>

                    {/* 已创建的角色 */}
                    {recognitionResult.created_characters.length > 0 && (
                      <div className="p-4 bg-purple-50 rounded-lg border border-purple-100">
                        <h4 className="text-sm font-medium text-purple-700 mb-2">
                          🎭 已创建 {recognitionResult.created_characters.length} 个角色
                        </h4>
                        {recognitionResult.created_characters.map((c) => (
                          <div key={c.id} className="mt-2 p-2 bg-white rounded border border-purple-100">
                            <p className="font-medium text-sm text-gray-900">{c.name}</p>
                            <p className="text-xs text-gray-600 mt-1">{c.description}</p>
                            <p className="text-xs text-gray-400 mt-1 italic">{c.appearance_prompt}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* 已创建的场景 */}
                    {recognitionResult.created_scenes.length > 0 && (
                      <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                        <h4 className="text-sm font-medium text-blue-700 mb-2">
                          🏞️ 已创建 {recognitionResult.created_scenes.length} 个场景
                        </h4>
                        {recognitionResult.created_scenes.map((s) => (
                          <div key={s.id} className="mt-2 p-2 bg-white rounded border border-blue-100">
                            <p className="font-medium text-sm text-gray-900">{s.name}</p>
                            <p className="text-xs text-gray-600 mt-1">{s.description}</p>
                            <p className="text-xs text-gray-400 mt-1 italic">{s.environment_prompt}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* 原始识别数据 */}
                    <details className="text-xs">
                      <summary className="text-gray-400 cursor-pointer">查看原始识别数据</summary>
                      <pre className="mt-2 p-3 bg-gray-50 rounded-lg overflow-auto max-h-60 text-gray-600">
                        {JSON.stringify(recognitionResult.recognition, null, 2)}
                      </pre>
                    </details>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ============ 角色表单 Modal ============ */}
      {showCharForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-auto">
          <div className="bg-white rounded-2xl w-full max-w-2xl mx-4 my-8 p-6 max-h-[90vh] overflow-auto">
            <h2 className="text-lg font-bold text-gray-900 mb-6">
              {editingChar ? "编辑角色" : "新建角色"}
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">角色名称 *</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  placeholder="如：布偶猫小花、红衣女主角"
                  value={charForm.name}
                  onChange={(e) => setCharForm({ ...charForm, name: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">角色描述（中文）</label>
                <textarea
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  rows={2}
                  placeholder="角色的基本介绍..."
                  value={charForm.description}
                  onChange={(e) => setCharForm({ ...charForm, description: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  外观提示词（中文，用于脚本生成）
                </label>
                <textarea
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  rows={2}
                  placeholder="详细的外观中文描述：一只蓝眼睛的布偶猫，奶油色皮毛，深褐色重点色..."
                  value={charForm.appearance_prompt_zh}
                  onChange={(e) => setCharForm({ ...charForm, appearance_prompt_zh: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Appearance Prompt（英文，用于 Seedance 视频生成）
                </label>
                <textarea
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 font-mono text-sm"
                  rows={3}
                  placeholder="a Ragdoll cat with blue eyes, cream-colored fur with dark brown points..."
                  value={charForm.appearance_prompt}
                  onChange={(e) => setCharForm({ ...charForm, appearance_prompt: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">默认语音</label>
                <select
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  value={charForm.voice_type}
                  onChange={(e) => setCharForm({ ...charForm, voice_type: e.target.value })}
                >
                  <option value="">不指定</option>
                  <option value="BV012_streaming">新闻男声</option>
                  <option value="BV700_streaming">灿灿</option>
                  <option value="BV701_streaming">擎苍</option>
                  <option value="BV001_streaming">通用女声</option>
                  <option value="BV002_streaming">通用男声</option>
                  <option value="BV411_streaming">影视解说小帅</option>
                  <option value="BV412_streaming">影视解说小美</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">标签</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="用逗号分隔，如：动物, 猫, 可爱"
                  value={charForm.tags}
                  onChange={(e) => setCharForm({ ...charForm, tags: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">参考图片</label>
                <FileUpload
                  accept="image/jpeg,image/png,image/webp"
                  label="上传角色参考图"
                  description="多张图片帮助 AI 保持一致性"
                  onUpload={handleCharImageUpload}
                />
                {charForm.reference_images.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {charForm.reference_images.map((url, i) => (
                      <div key={i} className="relative w-16 h-16 group">
                        <img src={url} alt="" className="w-full h-full object-cover rounded-lg border" />
                        <button
                          onClick={() =>
                            setCharForm((f) => ({
                              ...f,
                              reference_images: f.reference_images.filter((_, idx) => idx !== i),
                            }))
                          }
                          className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowCharForm(false)}
                className="px-4 py-2 text-gray-600 hover:text-gray-900"
              >
                取消
              </button>
              <button
                onClick={handleSaveChar}
                disabled={!charForm.name.trim()}
                className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                {editingChar ? "保存修改" : "创建角色"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============ 场景表单 Modal ============ */}
      {showSceneForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 overflow-auto">
          <div className="bg-white rounded-2xl w-full max-w-2xl mx-4 my-8 p-6 max-h-[90vh] overflow-auto">
            <h2 className="text-lg font-bold text-gray-900 mb-6">
              {editingScene ? "编辑场景" : "新建场景"}
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">场景名称 *</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="如：现代客厅、日落海滩"
                  value={sceneForm.name}
                  onChange={(e) => setSceneForm({ ...sceneForm, name: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">场景描述（中文）</label>
                <textarea
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  rows={2}
                  placeholder="场景的基本介绍..."
                  value={sceneForm.description}
                  onChange={(e) => setSceneForm({ ...sceneForm, description: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  环境提示词（中文，用于脚本生成）
                </label>
                <textarea
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  rows={2}
                  placeholder="温暖的现代客厅，木质地板，米色沙发..."
                  value={sceneForm.environment_prompt_zh}
                  onChange={(e) => setSceneForm({ ...sceneForm, environment_prompt_zh: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Environment Prompt（英文，用于 Seedance 视频生成）
                </label>
                <textarea
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                  rows={3}
                  placeholder="a cozy modern living room with warm wooden floors..."
                  value={sceneForm.environment_prompt}
                  onChange={(e) => setSceneForm({ ...sceneForm, environment_prompt: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">氛围</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    placeholder="温馨舒适"
                    value={sceneForm.mood}
                    onChange={(e) => setSceneForm({ ...sceneForm, mood: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">光照</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    placeholder="柔和自然光"
                    value={sceneForm.lighting}
                    onChange={(e) => setSceneForm({ ...sceneForm, lighting: e.target.value })}
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">标签</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="用逗号分隔，如：室内, 现代, 温馨"
                  value={sceneForm.tags}
                  onChange={(e) => setSceneForm({ ...sceneForm, tags: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">参考图片</label>
                <FileUpload
                  accept="image/jpeg,image/png,image/webp"
                  label="上传场景参考图"
                  description="帮助 AI 理解场景风格"
                  onUpload={handleSceneImageUpload}
                />
                {sceneForm.reference_images.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {sceneForm.reference_images.map((url, i) => (
                      <div key={i} className="relative w-16 h-16 group">
                        <img src={url} alt="" className="w-full h-full object-cover rounded-lg border" />
                        <button
                          onClick={() =>
                            setSceneForm((f) => ({
                              ...f,
                              reference_images: f.reference_images.filter((_, idx) => idx !== i),
                            }))
                          }
                          className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowSceneForm(false)}
                className="px-4 py-2 text-gray-600 hover:text-gray-900"
              >
                取消
              </button>
              <button
                onClick={handleSaveScene}
                disabled={!sceneForm.name.trim()}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {editingScene ? "保存修改" : "创建场景"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
