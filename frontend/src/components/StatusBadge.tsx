"use client";

interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  draft: { label: "草稿", color: "bg-gray-100 text-gray-700", icon: "📝" },
  scripting: { label: "脚本生成中", color: "bg-blue-100 text-blue-700", icon: "✍️" },
  generating: { label: "视频生成中", color: "bg-yellow-100 text-yellow-700", icon: "⏳" },
  composing: { label: "合成中", color: "bg-purple-100 text-purple-700", icon: "🎞️" },
  completed: { label: "已完成", color: "bg-green-100 text-green-700", icon: "✅" },
  failed: { label: "失败", color: "bg-red-100 text-red-700", icon: "❌" },
  // Shot statuses
  pending: { label: "待生成", color: "bg-gray-100 text-gray-600", icon: "⏸️" },
  queued: { label: "排队中", color: "bg-blue-50 text-blue-600", icon: "🔄" },
  running: { label: "运行中", color: "bg-yellow-100 text-yellow-700", icon: "⚡" },
  succeeded: { label: "成功", color: "bg-green-100 text-green-700", icon: "✅" },
  expired: { label: "已过期", color: "bg-orange-100 text-orange-700", icon: "⏰" },
};

export default function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] || { label: status, color: "bg-gray-100 text-gray-600", icon: "❓" };

  return (
    <span
      className={`
        inline-flex items-center gap-1 rounded-full font-medium
        ${config.color}
        ${size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm"}
      `}
    >
      <span>{config.icon}</span>
      <span>{config.label}</span>
    </span>
  );
}
