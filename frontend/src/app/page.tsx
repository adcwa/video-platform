"use client";

import { useEffect, useState } from "react";
import { api, type Project } from "@/lib/api";
import Link from "next/link";

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft: { label: "草稿", color: "bg-gray-100 text-gray-700" },
  scripting: { label: "脚本生成中", color: "bg-blue-100 text-blue-700" },
  generating: { label: "视频生成中", color: "bg-yellow-100 text-yellow-700" },
  composing: { label: "合成中", color: "bg-purple-100 text-purple-700" },
  completed: { label: "已完成", color: "bg-green-100 text-green-700" },
  failed: { label: "失败", color: "bg-red-100 text-red-700" },
};

export default function HomePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newProject, setNewProject] = useState({
    title: "",
    theme: "",
    scene_type: "entertainment",
    target_duration: 30,
    aspect_ratio: "16:9",
    resolution: "720p",
  });

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
      await api.createProject(newProject);
      setShowCreate(false);
      setNewProject({
        title: "",
        theme: "",
        scene_type: "entertainment",
        target_duration: 30,
        aspect_ratio: "16:9",
        resolution: "720p",
      });
      loadProjects();
    } catch (e) {
      console.error("创建项目失败:", e);
    }
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

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl w-full max-w-lg mx-4 p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-6">创建新项目</h2>

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
                  <select
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    value={newProject.scene_type}
                    onChange={(e) => setNewProject({ ...newProject, scene_type: e.target.value })}
                  >
                    <option value="entertainment">🎬 娱乐发布</option>
                    <option value="research">🔬 科研研究</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">目标时长(秒)</label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    min={5}
                    max={300}
                    value={newProject.target_duration}
                    onChange={(e) =>
                      setNewProject({ ...newProject, target_duration: parseInt(e.target.value) || 30 })
                    }
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">画面比例</label>
                  <select
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    value={newProject.aspect_ratio}
                    onChange={(e) => setNewProject({ ...newProject, aspect_ratio: e.target.value })}
                  >
                    <option value="16:9">16:9 横屏</option>
                    <option value="9:16">9:16 竖屏</option>
                    <option value="1:1">1:1 方形</option>
                    <option value="4:3">4:3</option>
                    <option value="3:4">3:4</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">分辨率</label>
                  <select
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    value={newProject.resolution}
                    onChange={(e) => setNewProject({ ...newProject, resolution: e.target.value })}
                  >
                    <option value="480p">480p</option>
                    <option value="720p">720p</option>
                    <option value="1080p">1080p</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-gray-600 hover:text-gray-900 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={!newProject.title.trim()}
                className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
