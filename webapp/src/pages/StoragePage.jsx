/**
 * 文件功能：
 * - 展示后端健康状态与存储后端运行信息。
 *
 * 执行逻辑：
 * 1. 并行查询 health 与 storage info。
 * 2. 在两者完成后统一渲染运行状态摘要。
 */

import { useQuery } from "@tanstack/react-query";
import { getStorageInfo } from "../api/settings";
import client from "../api/client";

/**
 * 获取服务健康状态。
 *
 * 输出：
 * - Promise<object>: 健康检查结果。
 */
async function getHealth() {
  return client.get("/api/health");
}

/**
 * 存储状态页面组件。
 *
 * Returns:
 * - JSX.Element: Storage 页面 UI。
 */
export default function StoragePage() {
  const storageQuery = useQuery({ queryKey: ["storage-info"], queryFn: getStorageInfo });
  const healthQuery = useQuery({ queryKey: ["health"], queryFn: getHealth });

  if (storageQuery.isLoading || healthQuery.isLoading) {
    return <p>Loading...</p>;
  }

  if (storageQuery.error) {
    return <p className="error">{storageQuery.error.message}</p>;
  }

  const info = storageQuery.data?.data;
  const health = healthQuery.data?.data?.status;

  return (
    <section>
      <h2>Storage</h2>
      <p>Service Health: {health}</p>
      <p>Environment: {info.environment}</p>
      <p>Vector Store: {info.default_vector_store}</p>
      <p>Chat Store: {info.default_chat_store}</p>
      <p>
        Redis: {info.redis.host}:{info.redis.port} / {info.redis.reachable ? "reachable" : "unreachable"}
      </p>
    </section>
  );
}
